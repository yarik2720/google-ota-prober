#!/usr/bin/python3

from checkin import checkin_generator_pb2
from google.protobuf import text_format
from utils import functions
import argparse, requests, gzip, shutil, os, yaml

parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', help='Print debug information to text file.')
parser.add_argument('--download', action='store_true', help='Download the OTA file.')
parser.add_argument('--fingerprint', help='Get the OTA using this fingerprint. Reading the config YML file is skipped.')
parser.add_argument('--model', help='Specify the model of the device. Required with --fingerprint.')
args = parser.parse_args()

class Prober:
    def __init__(self):
        pass

    def checkin(self, fingerprint: str, model: str, debug: bool = False) -> str:
        checkinproto = checkin_generator_pb2.AndroidCheckinProto()
        payload = checkin_generator_pb2.AndroidCheckinRequest()
        build = checkin_generator_pb2.AndroidBuildProto()
        response = checkin_generator_pb2.AndroidCheckinResponse()

        config = fingerprint.split('/')
        # Split "<device>:<android_version">
        temp = config[2].split(':')
        # Drop, then reinsert as two separate entries
        config.pop(2)
        config.insert(2, temp[0])
        config.insert(3, temp[1])
        current_build = config[4]
        android_version = config[3]
        device = config[2]
        self.headers = {
            'accept-encoding': 'gzip, deflate',
            'content-encoding': 'gzip',
            'content-type': 'application/x-protobuffer',
            'user-agent': f'Dalvik/2.1.0 (Linux; U; Android {android_version}; {model} Build/{current_build})'
        }

        # Add build properties
        build.id = fingerprint
        build.timestamp = 0
        build.device = device

        # Checkin proto
        checkinproto.build.CopyFrom(build)
        checkinproto.lastCheckinMsec = 0
        checkinproto.roaming = "WIFI::"
        checkinproto.userNumber = 0
        checkinproto.deviceType = 2
        checkinproto.voiceCapable = False
        checkinproto.unknown19 = "WIFI"

        # Generate the payload
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

        with gzip.open('test_data.gz', 'wb') as f_out:
            f_out.write(payload.SerializeToString())
            f_out.close()

        post_data = open('test_data.gz', 'rb')
        r = requests.post('https://android.googleapis.com/checkin', data=post_data, headers=self.headers)
        post_data.close()

        download_url = ""
        try:
            response.ParseFromString(r.content)
            if debug:
                with open('debug.txt', 'w') as f:
                    f.write(text_format.MessageToString(response))
                    f.close()
            setting = {entry.name: entry.value for entry in response.setting}
            update_title = setting.get(b'update_title', b'').decode()
            if update_title:
                print("Update title: " + setting.get(b'update_title', b'').decode())
            download_url = setting.get(b'update_url', b'').decode()
            if download_url:
                print("OTA URL obtained: " + download_url)
                return download_url
            else:
                print("No OTA URL found for your build. Either Google does not recognize your build fingerprint, or there are no new updates for your device.")
            return None
        except:
            print("Invalid fingerprint.")
            return None

    def checkin_cli(self) -> str:
        if args.fingerprint:
            if not args.model:
                print('You must specify a model with --model when using --fingerprint.')
                exit(1)
            else:
                return self.checkin(args.fingerprint, args.model, args.debug)
        else:
            with open('config.yml', 'r') as file:
                config = yaml.safe_load(file)
                file.close()
            return self.checkin(f'{config["oem"]}/{config["product"]}/{config["device"]}:{config["android_version"]}/{config["build_tag"]}/{config["incremental"]}:user/release-keys', config['model'], args.debug)
        
    def download(self, url: str) -> None:
        if url is None:
            return
        print("Downloading OTA file")
        with requests.get(url, stream=True) as resp:
            resp.raise_for_status()
            filename = url.split('/')[-1]

            total_size = int(resp.headers.get('content-length', 0))
            chunk_size = 1024

            with open(filename, 'wb') as file:
                progress = 0

                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        progress += len(chunk)
                        percentage = (progress / total_size) * 100
                        print(f"Downloaded {progress} of {total_size} bytes ({percentage:.2f}%)", end="\r")
            print(f"File downloaded and saved as {filename}!")


prober = Prober()
if args.download:
    prober.download(prober.checkin_cli())
else:
    prober.checkin_cli()