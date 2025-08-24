#!/usr/bin/env python
import requests
import time
import os
import sys
import argparse

# === CONFIG ===
VALID_MEDIA_TYPES = {"movies", "audio", "texts", "software", "image"}

def get_top_items(query_rows):
    url = "https://archive.org/advancedsearch.php"
    query = 'mediatype:("movies" OR "audio" OR "texts" OR "software" OR "data") AND format:torrent'

    params = {
        "q": query,
        "fl[]": "identifier,title,mediatype,week",
        "sort[]": "week desc",
        "rows": query_rows,
        "page": 1,
        "output": "json"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    docs = response.json()["response"]["docs"]

    return [(doc["identifier"], doc.get("title", "(no title)"), doc.get("mediatype", "")) for doc in docs]

def get_torrent_info(identifier):
    meta_url = f"https://archive.org/metadata/{identifier}"
    response = requests.get(meta_url)
    if response.status_code != 200:
        print(f"# Unexpected status_code={response.status_code} for meta_url={meta_url}", file=sys.stderr)
        return None

    metadata = response.json()
    files = metadata.get("files", [])

    torrent_url = ""
    for f in files:
        # archive.org can contain torrent files, but '_archive.torrent' are
        # (mostly) created by archive.org, though any user can upload their own
        # filename ending with '_archive.torrent', so, we should also verify
        # their tracker url's.
        if f.get("name", "").endswith("_archive.torrent"):
            next_torrent_url = f"https://archive.org/download/{identifier}/{f['name']}"
            if torrent_url != "" and torrent_url != next_torrent_url:
                print(f"# Unexpected multiple torrent_url's for meta_url={meta_url}", file=sys.stderr)
                print(torrent_url)
            torrent_url = next_torrent_url

    return torrent_url

def main():
    parser = argparse.ArgumentParser(description="Discover top --check-num-items of Archive.org weekly views ('week desc')")
    parser.add_argument('--check-num-items', type=int, default=100, help="Number of top items to examine for torrents")
                                     # Load banned identifiers if the file exists
    banned_identifiers = set()
    banned_fname = os.path.join(os.path.dirname(__file__), "files", "banned-archiveorg-identifiers.txt")
    with open(banned_fname, "r", encoding="utf-8") as f:
        banned_identifiers = {line.strip() for line in f if line.strip()}

    args = parser.parse_args()

    top_items = get_top_items(args.check_num_items)
    time.sleep(0.1)

    # _archive.torrent files *cannot be changed*, if internet archive screws up
    # a torrent, its screwed forever. If the contents of the archive change
    # (which is very common for their own metadata xml), the .torrent file is
    # not updated, and the official 'seeds' can no longer deliver them.
    #
    # conveniently, the torrent filename *always* matches the archive.org
    # 'identifier', so we can skip any metadata fetches that are already known.
    existing_torrents = [
            os.path.basename(f)[:-len('_archive.torrent')]
            for f in os.listdir(os.path.join(os.path.dirname(__file__), 'torrent-file-candidates'))
            if f.endswith('_archive.torrent')]

    for identifier, title, mediatype in top_items:
        # filter
        if (identifier in banned_identifiers) or (identifier in existing_torrents):
            continue
        # fetch
        torrent_url = get_torrent_info(identifier)

        # display
        if(torrent_url):
            print(f"# title={title} mediatype={mediatype}")
            print(torrent_url)
        else:
            print(f"# {identifier} - BAN CANDIDATE (no torrent) https://archive.org/details/{identifier}", file=sys.stderr)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
