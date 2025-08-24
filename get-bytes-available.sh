#!/bin/bash
#
# given the total size of the target volume, assume we can utilize $pct of it.
# then, subtracting size already allocated, how much is available for us to use?
pct=80

# you may want to change this to the volume of torrent downloads ..
destination_folder=`dirname $0`

# Get the mountpoint of the destination folder
mountpoint=$(df --output=target "$destination_folder" | tail -n 1)
if [ -z "$mountpoint" ]; then
    echo "Error: Could not determine mountpoint for $destination_folder"
    exit 1
fi

# Get disk usage information for the mountpoint
disk_info=$(df -k --output=size,used "$mountpoint" | tail -n 1)
if [ -z "$disk_info" ]; then
    echo "Error: Could not get disk usage information for $mountpoint"
    exit 1
fi

# Extract total size and used space (in KB)
total_kb=$(echo "$disk_info" | awk '{print $1}')
used_kb=$(echo "$disk_info" | awk '{print $2}')

# Convert KB to bytes
total_bytes=$((total_kb * 1024))
used_bytes=$((used_kb * 1024))

# Calculate 90% of total bytes
max_allowed_bytes=$((total_bytes * $pct / 100))

# Calculate available bytes within the 90% limit
if [ $used_bytes -lt $max_allowed_bytes ]; then
    bytes_avail=$((max_allowed_bytes - used_bytes))
else
    bytes_avail=0
fi

#echo "Mountpoint: $mountpoint"
#echo "   Total disk space: $total_bytes bytes"
#echo "         Used space: $used_bytes bytes"
#echo "  90% of Used space: $max_allowed_bytes bytes"
#echo "    Bytes available: $bytes_avail bytes"

echo $bytes_avail
