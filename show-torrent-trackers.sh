#!/bin/bash
if [ "$1" == "" ]; then
    echo "usage: $0 <filename.torrent>"
    exit 1
fi
transmission-show --info --trackers "$1" | \
  awk '
    # Skip empty lines, "TRACKERS", "WEBSEEDS", and "Tier #N" lines
    /^$/ || /^TRACKERS$/ || /^WEBSEEDS$/ || /^  Tier #[0-9]+$/ { next }
    # For remaining lines, remove leading whitespace (dedent)
    { sub(/^[[:space:]]+/, ""); print }
  ' | while read line; do
  echo "$(basename $1) # tracker=$line"
done
