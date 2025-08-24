#!/bin/bash

# read list of .torrent urls from stdin,
# save them to the same (basename) to output folder
# 
# url filenames must be unique, then !! careful !

dir=`dirname $0`/torrent-file-candidates
errors=0

while read -r url; do
  [ -z "$url" ] && continue

  # Skip comment lines starting with '#'
  [[ "$url" == \#* ]] && continue

  # Strip leading domain
  file="$(basename "$url")"

  # Check against banned filenames
  if [ -f "files/banned-torrent-filenames.txt" ]; then
    if grep -qFx "$file" "files/banned-torrent-filenames.txt"; then
      echo "Skipping banned filename: $file"
      continue
    fi
  fi

  # skip existing (archive.org torrents never update)
  if [ -f "$dir/$file" ]; then
      continue
  fi

  # Make directory if it doesn't exist
  mkdir -p "$dir"
  maybe_fetch=""
  if [ -f "$dir/$file" ]; then
     maybe_fetch="-z $dir/$file"
  fi

  # Download with curl: retry
  curl $maybe_fetch -fSL --no-progress-meter --retry 5 --retry-delay 5 --retry-max-time 300 -o "$dir/$file" "$url"
  errno=$?
  if [ $errno -ne 0 ]; then
      echo "errno=$errno for url=$url"
      errors=$(($errors + 1))
  fi
  sleep 0.1
done
echo "$errors errors"
if [ $errors -ne 0 ]; then
    exit 1
fi
