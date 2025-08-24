#!/usr/bin/env python3
import sys
import argparse
import re
import os

def parse_bytes(s):
    """Parse human-friendly byte strings like 10K, 5M, 1.5G"""
    if s is None:
        return None
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    match = re.match(r'^(\d+(?:\.\d+)?)([KMGTP]?)$', s.strip(), re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError(f"Invalid size: {s}")
    number, unit = match.groups()
    return int(float(number) * units.get(unit.upper(), 1))

def parse_database_line(line):
    """Parse a line from the torrent database file"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Format: identifier # N seeders, N leechers, N bytes [# errors...]
    parts = line.split(' # ', 2)
    if len(parts) < 2:
        return None
    
    identifier = parts[0].strip()
    stats_part = parts[1].strip()
    errors = parts[2].strip() if len(parts) > 2 else ""
    
    # Parse stats: "N seeders, N leechers, N bytes"
    stats_match = re.match(r'(\d+) seeders?, (\d+) leechers?, (\d+) bytes?', stats_part)
    if not stats_match:
        return None
    
    seeders = int(stats_match.group(1))
    leechers = int(stats_match.group(2))
    bytes_size = int(stats_match.group(3))
    peers = seeders + leechers  # peers = seeders + leechers
    
    return {
        'identifier': identifier,
        'seeders': seeders,
        'leechers': leechers,
        'peers': peers,
        'bytes': bytes_size,
        'errors': errors
    }

parser = argparse.ArgumentParser(description="Filter and sort torrents from database file by swarm stats and size")
parser.add_argument('--database', '-d', default='files/torrent-stats.db', 
                    help='Database file to read from (default: files/torrent-stats.db)')

group = parser.add_mutually_exclusive_group()
group.add_argument('--min-leeches', type=int)
group.add_argument('--max-leeches', type=int)

parser.add_argument('--min-seeds', type=int)
parser.add_argument('--max-seeds', type=int)
parser.add_argument('--min-peers', type=int)
parser.add_argument('--max-peers', type=int)
parser.add_argument('--min-bytes', type=parse_bytes)
parser.add_argument('--max-bytes', type=parse_bytes)
parser.add_argument('--max-total-bytes', type=parse_bytes,
                    help='Maximum total bytes to accumulate across all selected items')
parser.add_argument('--sort-by', choices=['leeches', 'seeds', 'peers', 'bytes'], default='leeches')
parser.add_argument('--max-count', type=int)
parser.add_argument('--display-urls', action='store_true')
parser.add_argument('--exclude-errors', action='store_true', 
                    help='Exclude entries with errors (no_tracker_response, etc.)')

args = parser.parse_args()

# Load banned identifiers if the file exists
banned_identifiers = set()
banned_file_path = os.path.join(os.path.dirname(__file__), "files", "banned-archiveorg-identifiers.txt")
try:
    with open(banned_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                banned_identifiers.add(line)
except FileNotFoundError:
    # If banned file doesn't exist, continue without filtering
    pass

# Read and parse database file
results = []
total_bytes_accumulated = 0
try:
    with open(args.database, 'r') as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_database_line(line)
            if parsed is None:
                continue
            
            # Skip banned identifiers
            if parsed['identifier'] in banned_identifiers:
                continue
            
            # Apply filters
            leeches = parsed['leechers']
            seeds = parsed['seeders']
            peers = parsed['peers']
            size = parsed['bytes']
            errors = parsed['errors']
            
            # Skip entries with errors if requested
            if args.exclude_errors and errors:
                continue
            
            if args.min_leeches is not None and leeches < args.min_leeches:
                continue
            if args.max_leeches is not None and leeches > args.max_leeches:
                continue
            if args.min_seeds is not None and seeds < args.min_seeds:
                continue
            if args.max_seeds is not None and seeds > args.max_seeds:
                continue
            if args.min_peers is not None and peers < args.min_peers:
                continue
            if args.max_peers is not None and peers > args.max_peers:
                continue
            if args.min_bytes is not None and size < args.min_bytes:
                continue
            if args.max_bytes is not None and size > args.max_bytes:
                continue
            
            # Check if adding this item would exceed max total bytes
            if args.max_total_bytes is not None:
                if total_bytes_accumulated + size > args.max_total_bytes:
                    continue  # Skip this item as it would exceed the total limit
                
            results.append(parsed)
            
            # Update total bytes accumulated
            if args.max_total_bytes is not None:
                total_bytes_accumulated += size
            
            # Stop if we hit max count
            if args.max_count is not None and len(results) >= args.max_count:
                break

except FileNotFoundError:
    print(f"[ERROR] Database file '{args.database}' not found", file=sys.stderr)
    print("Create it first with: ./build-torrent-database.py -o files/torrent-stats.db", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Failed to read database: {e}", file=sys.stderr)
    sys.exit(1)

# Sort results
sort_key = args.sort_by
if sort_key == 'seeds':
    sort_key = 'seeders'
elif sort_key == 'leeches':
    sort_key = 'leechers'

results.sort(key=lambda x: x[sort_key], reverse=True)

# Limit results if max_count specified
if args.max_count is not None:
    results = results[:args.max_count]

# Print output
for r in results:
    if args.display_urls:
        txt_obj = f"https://archive.org/download/{r['identifier']}/{r['identifier']}_archive.torrent"
        txt_linkvar = f"identifier={r['identifier']}"
    else:
        txt_obj = f"{r['identifier']}"
        txt_linkvar = f"name={r['identifier']}"
    
    error_info = f" errors={r['errors']}" if r['errors'] else ""
    print(f"{txt_obj} # leeches={r['leechers']} seeds={r['seeders']} peers={r['peers']} size={r['bytes']} {txt_linkvar}{error_info}")
