#!/usr/bin/env python3
#
# This is just a wrapper around transmission-show CLI, to combine
# filesize and "scrape" peer statistics from torrent trackers and
# output to a single, machine-parsable STDOUT as, f"<id> # <n> seeders, <h> leechers, <n> bytes{comment}")
import sys
import subprocess
import re
import argparse
from pathlib import Path

def extract_identifier_from_filename(filename):
    """Extract identifier from filename by removing _archive.torrent suffix"""
    basename = Path(filename).name
    if basename.endswith('_archive.torrent'):
        return basename[:-16]  # Remove '_archive.torrent'
    return basename

def parse_scrape_output(scrape_output):
    """Parse transmission-show -s output to extract seeders and leechers"""
    seeders = 0
    leechers = 0
    errors = []
    
    lines = scrape_output.strip().split('\n')
    for line in lines:
        if 'scrape?' in line:
            if 'no match' in line.lower():
                errors.append("no_tracker_response")
            elif 'error' in line.lower():
                errors.append("tracker_error")
            else:
                # Try to extract seeders/leechers if present in response
                # Format is like: "... 0 seeders, 1 leechers"
                seeders_match = re.search(r'(\d+)\s+seeders?', line, re.IGNORECASE)
                leechers_match = re.search(r'(\d+)\s+leechers?', line, re.IGNORECASE)
                if seeders_match:
                    seeders = max(seeders, int(seeders_match.group(1)))
                if leechers_match:
                    leechers = max(leechers, int(leechers_match.group(1)))
    
    return seeders, leechers, errors

def parse_bytes_output(bytes_output):
    """Parse transmission-show -b output to extract total bytes"""
    total_bytes = 0
    errors = []
    
    lines = bytes_output.strip().split('\n')
    for line in lines:
        if 'Total Size:' in line:
            # Extract size like "Total Size: 160.1 kB"
            size_match = re.search(r'Total Size:\s*([\d.,]+)\s*([KMGTPE]?B)', line)
            if size_match:
                value, unit = size_match.groups()
                value = float(value.replace(',', ''))
                
                # Convert to bytes
                multipliers = {
                    'B': 1,
                    'KB': 1024,
                    'MB': 1024**2, 
                    'GB': 1024**3,
                    'TB': 1024**4,
                    'PB': 1024**5,
                    'EB': 1024**6,
                    'kB': 1024,  # transmission uses kB for KB
                    'KiB': 1024,
                    'MiB': 1024**2,
                    'GiB': 1024**3,
                    'TiB': 1024**4,
                }
                
                multiplier = multipliers.get(unit, 1)
                total_bytes = int(value * multiplier)
                break
    
    if total_bytes == 0:
        errors.append("no_size_found")
    
    return total_bytes, errors

def process_torrent_file(torrent_file):
    """Process a single torrent file and return stats"""
    identifier = extract_identifier_from_filename(torrent_file)
    seeders = 0
    leechers = 0 
    total_bytes = 0
    errors = []
    
    # Get scrape data (seeders/leechers)
    try:
        result = subprocess.run(['transmission-show', '-s', torrent_file], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            seeders, leechers, scrape_errors = parse_scrape_output(result.stdout)
            errors.extend(scrape_errors)
        else:
            errors.append(f"scrape_failed_rc{result.returncode}")
            if result.stderr:
                errors.append(f"scrape_stderr:{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        errors.append("scrape_timeout")
    except Exception as e:
        errors.append(f"scrape_error:{str(e)}")
    
    # Get size data
    try:
        result = subprocess.run(['transmission-show', '-b', torrent_file],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            total_bytes, size_errors = parse_bytes_output(result.stdout)
            errors.extend(size_errors)
        else:
            errors.append(f"size_failed_rc{result.returncode}")
            if result.stderr:
                errors.append(f"size_stderr:{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        errors.append("size_timeout")
    except Exception as e:
        errors.append(f"size_error:{str(e)}")
    
    return identifier, seeders, leechers, total_bytes, errors

def main():
    parser = argparse.ArgumentParser(description='Build torrent statistics database using transmission-show')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output to stderr')
    parser.add_argument('torrent_file', nargs='?', help='Torrent file to process (default: read from stdin)')
    
    args = parser.parse_args()
    
    # Input source - either command line argument or stdin
    if args.torrent_file:
        torrent_file = args.torrent_file.strip()
    else:
        # Read single line from stdin
        torrent_file = sys.stdin.readline().strip()
    
    if not torrent_file:
        return
    
    if args.verbose:
        print(f"Processing: {torrent_file}", file=sys.stderr)
    
    if not Path(torrent_file).exists():
        identifier = extract_identifier_from_filename(torrent_file)
        print(f"{identifier} # 0 seeders, 0 leechers, 0 bytes # file_not_found")
        return
    
    identifier, seeders, leechers, total_bytes, errors = process_torrent_file(torrent_file)
    
    # Format output line
    comment_parts = []
    if errors:
        comment_parts.extend(errors)
    
    comment = ""
    if len(comment_parts) > 0:
        comment = " # " + " ".join(comment_parts)
    
    print(f"{identifier} # {seeders} seeders, {leechers} leechers, {total_bytes} bytes{comment}")

if __name__ == '__main__':
    main()
