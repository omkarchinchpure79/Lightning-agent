import urllib.request
import re
import base64
import os
import ssl
import time
import json

# Target directory
OUTPUT_DIR = "data/raw/pdfs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# SSL context to bypass verification errors
SSL_CONTEXT = ssl._create_unverified_context()

# Request headers to look like a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Download direct PDF URL
def download_direct(url, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        print(f"File already exists, skipping: {filename}")
        return True
        
    print(f"Downloading static PDF: {url} -> {filename}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
            data = response.read()
            
        if data.startswith(b"%PDF-"):
            with open(filepath, "wb") as f:
                f.write(data)
            print(f"  [SUCCESS] Saved {len(data)} bytes.")
            return True
        else:
            print(f"  [ERROR] Data from {url} is not a valid PDF! Starts with: {data[:20]}")
            return False
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {str(e)}")
        return False

# Download base64 embedded PDF
def download_base64(url, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        print(f"File already exists, skipping: {filename}")
        return True
        
    print(f"Extracting base64 PDF: {url} -> {filename}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        pattern = r"LoadPublicDocument\s*\(\s*'([^']+)'\s*\)"
        matches = re.findall(pattern, html)
        if not matches:
            print(f"  [ERROR] LoadPublicDocument call not found in HTML response from {url}")
            return False
            
        base64_str = matches[0].strip()
        pdf_data = base64.b64decode(base64_str)
        
        if pdf_data.startswith(b"%PDF-"):
            with open(filepath, "wb") as f:
                f.write(pdf_data)
            print(f"  [SUCCESS] Decoded and saved {len(pdf_data)} bytes.")
            return True
        else:
            print(f"  [ERROR] Decoded data is not a valid PDF! Starts with: {pdf_data[:20]}")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Failed to extract from {url}: {str(e)}")
        return False

# --- Wayback Machine archival downloads (2019-2022, roadmap item A1) --------
# The live portals for these years are dead (fe2023.mahacet.org is now a parked
# Plesk page). Cutoff PDFs for year Y were originally hosted on the NEXT year's
# portal (fe{Y+1}.mahacet.org/{Y}/...) — confirmed via the CDX API, same
# {year}ENGG_CAP{n}[_AI]_CutOff.pdf naming CET Cell has always used. We query
# the CDX API at runtime (never hardcode a snapshot timestamp — those can go
# stale or point at a redirect/interstitial capture) and fetch the raw bytes
# via the "id_" suffix, which serves the archived resource directly instead of
# the Wayback toolbar wrapper page.
CDX_API = "http://web.archive.org/cdx/search/cdx"


def _cdx_lookup(original_url, retries=4):
    """Return the timestamp of the best (mimetype=pdf, status=200) snapshot for
    `original_url`, or None if it was never archived. Prefers the LATEST capture
    (most likely to be complete; PDFs don't change once published).

    archive.org's CDX endpoint is flaky under repeated rapid querying (503s and
    timeouts are common, not a sign the snapshot doesn't exist) — retry with
    backoff before concluding there's genuinely nothing archived."""
    query = f"{CDX_API}?url={original_url}&output=json&filter=mimetype:application/pdf&filter=statuscode:200"
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(query, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as resp:
                rows = json.loads(resp.read())
            if len(rows) < 2:  # row 0 is the header; genuinely no archived snapshot
                return None
            return rows[-1][1]  # timestamp column, last (= latest) row
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))  # 3s, 6s, 9s backoff
    print(f"  [CDX ERROR] {original_url}: {last_err} (after {retries} attempts)")
    return None


def download_wayback(year, cap_num, variant, filename):
    """variant: 'MH' or 'AI'. Looks up the archived snapshot via CDX, then
    downloads the raw PDF bytes via the id_ (raw resource) suffix."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        print(f"File already exists, skipping: {filename}")
        return True

    suffix = "_AI" if variant == "AI" else ""
    original_url = f"https://fe{year + 1}.mahacet.org/{year}/{year}ENGG_CAP{cap_num}{suffix}_CutOff.pdf"

    timestamp = _cdx_lookup(original_url)
    if timestamp is None:
        print(f"  [SKIP] No archived snapshot for {original_url} (this round/variant may not exist for {year}).")
        return False

    archive_url = f"http://web.archive.org/web/{timestamp}id_/{original_url}"

    # archive.org resets the connection mid-transfer on a meaningful fraction of
    # larger files (observed: several PDFs silently truncated at exactly 1 MiB,
    # started with a valid %PDF- header so the old startswith-only check missed
    # it). Retry the actual byte transfer, and verify BOTH the Content-Length
    # header (when present) and the %%EOF trailer every well-formed PDF ends
    # with — a truncated response fails one of those even if the magic bytes
    # happened to survive.
    for attempt in range(4):
        print(f"Downloading from Wayback Machine: {archive_url} -> {filename} (attempt {attempt + 1})")
        try:
            req = urllib.request.Request(archive_url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=60) as response:
                expected_len = response.headers.get("Content-Length")
                data = response.read()
        except Exception as e:
            print(f"  [ERROR] Transfer failed: {e}")
            if attempt < 3:
                time.sleep(4 * (attempt + 1))
            continue

        if not data.startswith(b"%PDF-"):
            print(f"  [ERROR] Data is not a valid PDF! Starts with: {data[:20]}")
            return False
        if expected_len is not None and len(data) != int(expected_len):
            print(f"  [ERROR] Truncated: got {len(data)} bytes, expected {expected_len}. Retrying.")
            if attempt < 3:
                time.sleep(4 * (attempt + 1))
            continue
        if b"%%EOF" not in data[-2048:]:
            print(f"  [ERROR] No %%EOF trailer in the last 2KB — likely truncated. Retrying.")
            if attempt < 3:
                time.sleep(4 * (attempt + 1))
            continue

        with open(filepath, "wb") as f:
            f.write(data)
        print(f"  [SUCCESS] Saved {len(data)} bytes (archived {timestamp}).")
        return True

    print(f"  [ERROR] Giving up on {archive_url} after 4 attempts.")
    return False


def download_wayback_years(years=(2019, 2020, 2021, 2022), rounds=(1, 2, 3)):
    """Attempts CAP1-3, MH+AI for each year. Not every year has every round/variant
    (e.g. 2020 has no CAP2_AI) — download_wayback returns False and is skipped
    gracefully rather than guessed, matching the fail-closed data rule."""
    success_count = 0
    attempted = 0
    for year in years:
        print(f"\n--- Wayback cycle {year} ---")
        for cap_num in rounds:
            for variant in ("MH", "AI"):
                filename = f"{year}_CAP{cap_num}_{variant}.pdf"
                attempted += 1
                if download_wayback(year, cap_num, variant, filename):
                    success_count += 1
                time.sleep(5)  # polite delay to archive.org (CDX rate-limits aggressively)
    print(f"\nWayback download completed: {success_count}/{attempted} files "
          f"downloaded (some round/variant combinations legitimately don't exist "
          f"for every year).")
    return success_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download MHT-CET cutoff PDFs.")
    parser.add_argument("--wayback", action="store_true",
                        help="Also fetch 2019-2022 from the Wayback Machine "
                             "(the live 2023-2025 portals are downloaded regardless).")
    parser.add_argument("--wayback-only", action="store_true",
                        help="Fetch ONLY 2019-2022 from the Wayback Machine, skip 2023-2025.")
    args = parser.parse_args()

    if args.wayback_only:
        download_wayback_years()
        return True

    print("Starting download of all MHT CET cutoff PDFs (2023 - 2025)...")

    # 2023 MH Cutoffs (Direct static URLs)
    urls_2023 = {
        "2023_CAP1_MH.pdf": "https://fe2024.mahacet.org/2023/2023ENGG_CAP1_CutOff.pdf",
        "2023_CAP2_MH.pdf": "https://fe2024.mahacet.org/2023/2023ENGG_CAP2_CutOff.pdf",
        "2023_CAP3_MH.pdf": "https://fe2024.mahacet.org/2023/2023ENGG_CAP3_CutOff.pdf"
    }
    
    # base64 MenuIds mapped to descriptive filenames
    # Schema: (year, domain) -> { filename: menu_id }
    base64_configs = {
        ("2024", "https://fe2024.mahacet.org/"): {
            "2024_CAP1_MH.pdf": "2449",
            "2024_CAP1_AI.pdf": "2450",
            "2024_CAP2_MH.pdf": "3475",
            "2024_CAP2_AI.pdf": "3476",
            "2024_CAP3_MH.pdf": "3483",
            "2024_CAP3_AI.pdf": "3484"
        },
        ("2025", "https://fe2025.mahacet.org/"): {
            "2025_CAP1_MH.pdf": "2449",
            "2025_CAP1_AI.pdf": "2450",
            "2025_CAP2_MH.pdf": "3475",
            "2025_CAP2_AI.pdf": "3476",
            "2025_CAP3_MH.pdf": "3483",
            "2025_CAP3_AI.pdf": "3484",
            "2025_CAP4_MH.pdf": "9822",
            "2025_CAP4_AI.pdf": "9823"
        }
    }
    
    success_count = 0
    total_count = len(urls_2023) + sum(len(cfg) for cfg in base64_configs.values())
    
    # Download 2023
    print("\n--- Cycle 2023 ---")
    for filename, url in urls_2023.items():
        if download_direct(url, filename):
            success_count += 1
        time.sleep(1) # Polite delay
        
    # Download 2024 and 2025
    for (year, domain), mapping in base64_configs.items():
        print(f"\n--- Cycle {year} ---")
        for filename, menu_id in mapping.items():
            url = f"{domain}ViewPublicDocument.aspx?MenuId={menu_id}"
            if download_base64(url, filename):
                success_count += 1
            time.sleep(1) # Polite delay
            
    print(f"\nDownload completed: {success_count}/{total_count} files downloaded successfully.")

    if args.wayback:
        download_wayback_years()

    return success_count == total_count

if __name__ == "__main__":
    main()
