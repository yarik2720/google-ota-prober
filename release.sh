#!/bin/bash
if [ -f update_info.json ]; then
      configs=$(jq -r 'keys[]' update_info.json)
      for config in $configs
      do
        new_update=$(jq -r ".[\"$config\"].found" update_info.json)
        if [ "$new_update" = "true" ]; then
          update_title=$(jq -r ".[\"$config\"].title" update_info.json)
          tag_name=$(jq -r ".[\"$config\"].tag_name" update_info.json)
          update_device=$(jq -r ".[\"$config\"].device" update_info.json)
          update_description=$(jq -r ".[\"$config\"].description" update_info.json)
          update_url=$(jq -r ".[\"$config\"].url" update_info.json)
          update_size=$(jq -r ".[\"$config\"].size" update_info.json)
          update_fingerprint=$(jq -r ".[\"$config\"].fingerprint" update_info.json)

          # Prepare release notes with proper Markdown formatting
          if [ "$update_fingerprint" != "null" ] && [ -n "$update_fingerprint" ]; then
            fingerprint_note="**Fingerprint:** $update_fingerprint"
          else
            fingerprint_note=""
          fi
          release_notes="
# $update_device ($tag_name)

## Changelog:
$update_description

$fingerprint_note

**Size:** $update_size

**Download URL:** $update_url
"

      # Check if release with this tag exists
      if ! gh release view "$tag_name" &> /dev/null; then
        gh release create "$tag_name" \
              --title "$tag_name" \
              --notes "$release_notes"
            echo "Created new release: $tag_name for config $config"
          else
            echo "Release '$tag_name' for config $config already exists. Skipping."
          fi
        else
          echo "No new updates found for config $config"
        fi
    done
else
    echo "update_info.json not found. This might be the first run."
fi
