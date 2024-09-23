#!/usr/bin/python3

import argparse
import gzip
import os
import subprocess
import yaml
import requests
from google.protobuf import text_format
from checkin import checkin_generator_pb2
from utils import functions

def load_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Print debug information to text file.')
    parser.add_argument('-c', '--config', default='config.yml', help='Path to the config file')
    parser.add_argument('--download', action='store_true', help='Download the OTA file.')
    return parser.parse_args()

def create_headers(android_version, model, current_build):
    return {
        'accept-encoding': 'gzip, deflate',
        'content-encoding': 'gzip',
        'content-type': 'application/x-protobuffer',
        'user-agent': f'Dalvik/2.1.0 (Linux; U; Android {android_version}; {model} Build/{current_build})'
    }

def create_payload(config):
    build = checkin_generator_pb2.AndroidBuildProto()
    build.id = f'{config["oem"]}/{config["product"]}/{config["device"]}:{config["android_version"]}/{config["build_tag"]}/{config["incremental"]}:user/release-keys'
    build.timestamp = 0
    build.device = config['device']

    checkinproto = checkin_generator_pb2.AndroidCheckinProto()
    checkinproto.build.CopyFrom(build)
    checkinproto.lastCheckinMsec = 0
    checkinproto.roaming = "WIFI::"
    checkinproto.userNumber = 0
    checkinproto.deviceType = 2
    checkinproto.voiceCapable = False
    checkinproto.unknown19 = "WIFI"

    payload = checkin_generator_pb2.AndroidCheckinRequest()
    payload.imei = functions.generateImei()
    payload.id = 0
    payload.digest = functions.generateDigest()
    payload.checkin.CopyFrom(checkinproto)
    payload.locale = 'en-US'
    payload.macAddr.append(functions.generateMac())
    payload.timeZone = 'America/New_York'
    payload.version = 3
    payload.serialNumber = functions.generateSerial()
    payload.macAddrType.append('wifi')
    payload.fragment = 0
    payload.userSerialNumber = 0
    payload.fetchSystemUpdates = 1
    payload.unknown30 = 0

    return payload

def send_request(payload, headers):
    with gzip.open('test_data.gz', 'wb') as f_out:
        f_out.write(payload.SerializeToString())

    with open('test_data.gz', 'rb') as post_data:
        return requests.post('https://android.googleapis.com/checkin', data=post_data, headers=headers)

def process_response(response, args):
    if args.debug:
        with open('debug.txt', 'w') as f:
            f.write(text_format.MessageToString(response))

    download_url = next((entry.value.decode() for entry in response.setting if b'https://android.googleapis.com' in entry.value), None)
    
    if download_url:
        update_title = next((entry.value.decode() for entry in response.setting if entry.name.decode() == "update_title"), None)
        
        if check_existing_release(update_title):
            return None
        
        print("\nUpdate found....")
        update_description = next((entry.value.decode() for entry in response.setting if entry.name.decode() == "update_description"), None)
        update_size = next((entry.value.decode() for entry in response.setting if entry.name.decode() == "update_size"), None)

        print(f"\nTITLE:\n{update_title}")
        print(f"\nCHANGELOG:\n{update_description}")
        print(f"\nOTA URL obtained: {download_url}")
        print(f"SIZE: {update_size}")
        
        return download_url
    else:
        print("There are no new updates for your device.")
        return None

def check_existing_release(update_title):
    try:
        subprocess.run(
            ["gh", "release", "view", update_title],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        print(f"Release with title '{update_title}' already exists. Skipping update.")
        return True
    except subprocess.CalledProcessError:
        return False

def download_ota(download_url):
    print("Downloading OTA file")
    with requests.get(download_url, stream=True) as resp:
        resp.raise_for_status()
        filename = download_url.split('/')[-1]

        total_size = int(resp.headers.get('content-length', 0))
        chunk_size = 1024

        with open(filename, 'wb') as file:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    file.write(chunk)
                    progress = file.tell()
                    percentage = (progress / total_size) * 100
                    print(f"Downloaded {progress} of {total_size} bytes ({percentage:.2f}%)", end="\r")
        print(f"\nFile downloaded and saved as {filename}!")

def main():
    args = parse_arguments()
    config = load_config(args.config)

    print(f"Checking device... {config['model']}")
    print(f"Current version... {config['incremental']}")
    fp = f'{config["oem"]}/{config["product"]}/{config["device"]}:{config["android_version"]}/{config["build_tag"]}/{config["incremental"]}:user/release-keys'
    print("Fingerprint... " + fp)

    headers = create_headers(config['android_version'], config['model'], config['build_tag'])
    payload = create_payload(config)

    try:
        r = send_request(payload, headers)
        response = checkin_generator_pb2.AndroidCheckinResponse()
        response.ParseFromString(r.content)

        download_url = process_response(response, args)
        
        if download_url and args.download:
            download_ota(download_url)
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
