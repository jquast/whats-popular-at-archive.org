Requires
========

`apt-get install transmission-cli qbittorrent pv parallel`

qbittorrent preferences,

- enable 'Web User Interface' under 'Web UI'
- and also enable 'Bypass authentication for clients on localhost' under 'WEB UI'
- also suggest to enable 'Pre-Allocate disk space for all files' under 'Downloads'

Programs
========

`run.sh` orchestrates and runs all of the following programs, mostly in this order.

The final step in run.sh calls "open" on the .torrent files that match the given criteria,
it is expected these are associated with qbittorrent by your OS, and, you can then preview
and evaluate whether to continue to start it from there.

- `fetch-top-torrents-urls.py`: fetch torrent url's from archive.org for "what's popular"
- `gentle-fetch-torrent-files.sh`: "gently" fetches .torrent files from url's
- `show-torrent-trackers.sh`: displays tracker urls for .torrent file
- `get-bytes-available.sh`: determine available disk space for torrents
- `build-torrent-database.py`: scrapes tracker information to machine-readable output
- `db-list-filtered.py`: query the text database of torrents tracker information

Data
====

- `torrent-file-candidates/`: folder containing candidate .torrent files
- `files/popular-torrent-urls.txt`: list of popular archive.org items by their torrent urls
- `files/banned-identifiers.txt`: list of archive org identifiers that are ignored
- `files/torrent-stats.db`: machine-readable torrent statistics
