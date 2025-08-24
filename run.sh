#!/bin/bash
set -o errexit
set -o pipefail

# requires transmission-cli ..

keepFreshArchiveOrgTopNHours=12
topPopularArchiveOrgEvaluateNum=2000

numParallelScrapers=8
keepFreshStatsDbNHours=12

filePopularTorrentUrls=files/popular-torrent-urls.txt
max_torrent_count=100
max_torrent_size=512G
min_torrent_peers=6
torrentStatsDb="files/torrent-stats.txt"

# Check if torrent URLs file needs updating (only if more than 12 hours old)
should_update=1
if [ -f "$filePopularTorrentUrls" ]; then
    # Get the last modified time in seconds since epoch
    last_modified_epoch=$(date -r "$filePopularTorrentUrls" +%s)
    current_time_epoch=$(date +%s)
    
    # Calculate the difference in seconds (12 hours = = 43200 seconds)
    keepFreshArchiveOrgTopNSeconds=$((12 * 60 * 60 * keepFreshArchiveOrgTopNHours))
    time_diff=$((current_time_epoch - last_modified_epoch))
    if [ $time_diff -lt $keepFreshArchiveOrgTopNSeconds ]; then
        echo "* Torrent URLs file is less than 12 hours old (${time_diff}s ago) -- SKIP $filePopularTorrentUrls"
        should_update=0
    else
        echo "* Torrent URLs file is more than 12 hours old (${time_diff}s ago), WILL UPDATE $filePopularTorrentUrls"
    fi
fi

if [ $should_update -eq 1 ]; then
    # backup previous popular torrent url
    if [ -f "files/popular-torrent-urls.txt" ]; then
        last_modified=$(date -r "files/popular-torrent-urls.txt" +%Y%m%d)
        mv "files/popular-torrent-urls.txt" "files/popular-torrent-urls.txt.$last_modified"
    fi

    # fetch torrent url's of popular items viewed on archive.org,
    # *in the past week*, a static query offered by their API for "what is popular
    # lately"
    python fetch-top-torrents-urls.py \
        --check-num-items="${topPopularArchiveOrgEvaluateNum}" \
        | pv -l \
        > "$filePopularTorrentUrls" 2>&1
else
    echo "* Using existing torrent URLs file (files/popular-torrent-urls.txt)."
fi

# and then download them. Some of them have errors. Clicking some of their URL's may be
# possible to download, only if logged in (403 ..)
echo "* Fetching torrent files from archive.org"
retcode=0
pv -l files/popular-torrent-urls.txt | ./gentle-fetch-torrent-files.sh || retcode=$?
echo "retcode=$retcode"

# and finally farm all of their trackers, using only files
# modified in the last 7 days (oldest retire out)
find torrent-file-candidates/ -mtime 7 -name '*_archive.torrent' \
| pv -l | while read f; do
    filename="$(basename "$f")"
    identifier="${filename%_*}"   # Removes everything after the last '_' ("_archive.torrent") # skip ignored ..

    # banned ! mostly we ignore some things on purpose, non-archive.org torrent,
    # or, because 403 or something,
    if grep "$identifier" files/banned-identifiers.txt >/dev/null; then
        continue
    fi

    # refresh list of trackers -- only one time should be necessary
    if [ ! -f "$f.trackers" ]; then
       ./show-torrent-trackers.sh "$f" > "$f.trackers"
    fi

    # check that *all* trackers contain phrase 'archive.org'
    retcode=0
    grep -v "archive.org" "$f.trackers" >/dev/null || retcode=$?
    # if not -- non-archive.org exists, it becomes banned !
    if [ $retcode -eq 0 ]; then
        echo -e "# non-archive.org trackers (automated)\n$identifier" | tee -a files/banned-identifiers.txt
    fi
done

# and maximum total storage size for any new downloads
avail_bytes=$(`dirname $0`/get-bytes-available.sh)
if [ $avail_bytes -le 0 ]; then
    echo "* No bytes available! avail_bytes=$avail_bytes"
    exit 0
else
    echo "* Proceeding with avail_bytes=$avail_bytes"
fi

echo "* (always) re-Applying banned filter"
# always re-apply final filter to exclude banned identifiers,
find torrent-file-candidates/ -name '*_archive.torrent' | while read f; do
    filename="$(basename "$f")"
    identifier="${filename%_*}"   # Removes everything after the last '_' ("_archive.torrent")
    # Only include if identifier is NOT in banned list
    if ! grep -q "^$identifier$" files/banned-identifiers.txt 2>/dev/null; then
        echo "$f"
    fi
done \
| pv -l \
> files/torrent-files-allowed.txt

doScrape=1
if [ -f "$torrentStatsDb" ]; then
    last_modified_epoch=$(date -r "$torrentStatsDb" +%s)
    current_time_epoch=$(date +%s)
    time_diff=$((current_time_epoch - last_modified_epoch))
    keepFreshStatsDbNSeconds=$((12 * 60 * 60 * keepFreshStatsDbNHours))
    if [ $time_diff -lt $keepFreshStatsDbNSeconds ]; then
        echo "Skipping update - $torrentStatsDb was modified within the last 12 hours"
        doScrape=0
    fi
fi
if [ $doScrape -eq 1 ]; then
   echo "Scraping trackers to $torrentStatsDb"
   cat files/torrent-files-allowed.txt \
      | parallel -j $numParallelScrapers --line-buffer \
        python ./build-torrent-database.py \
      | pv -l > $torrentStatsDb
fi

# query database of torrent files to fit our restraints of available disk and popularity.
echo "Performing query on $torrentStatsDb, popular torrents will open !"
./db-list-filtered.py \
    --database $torrentStatsDb \
    --min-peers=$min_torrent_peers \
    --min-bytes=10M \
    --max-bytes=$max_torrent_size \
    --max-count=$max_torrent_count \
    --sort-by=bytes \
    --max-total-bytes=$avail_bytes \
| while read id others; do
    fname="torrent-file-candidates/${id}_archive.torrent"
    echo $fname: $others
    open "torrent-file-candidates/${id}_archive.torrent"
    sleep 0.1
done
