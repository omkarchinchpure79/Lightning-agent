import urllib.request
import urllib.error
import re
import ssl

def check_link(year_url, menu_id):
    url = f"{year_url}ViewPublicDocument.aspx?MenuId={menu_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        pattern = r"LoadPublicDocument\s*\(\s*'([^']+)'\s*\)"
        matches = re.findall(pattern, html)
        if matches:
            print(f"  [SUCCESS] MenuId={menu_id} on {year_url} exists. base64 size: {len(matches[0])}")
            return True
        else:
            # Let's check if the page loaded but had no document, or if it was an error
            print(f"  [WARNING] MenuId={menu_id} loaded on {year_url} but no LoadPublicDocument found. HTML len: {len(html)}")
            # Check if there is an iframe or another element
            if "ViewPublicDocument" in html:
                print(f"    Page contains ViewPublicDocument text")
            return False
    except urllib.error.HTTPError as e:
        print(f"  [FAILED] MenuId={menu_id} on {year_url} returned HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  [ERROR] MenuId={menu_id} on {year_url}: {str(e)}")
        return False

if __name__ == "__main__":
    portals = {
        "2023": "https://fe2023.mahacet.org/",
        "2024": "https://fe2024.mahacet.org/",
        "2025": "https://fe2025.mahacet.org/"
    }
    
    menu_ids = {
        "CAP 1 MH": "2449",
        "CAP 1 AI": "2450",
        "CAP 2 MH": "3475",
        "CAP 2 AI": "3476",
        "CAP 3 MH": "3483",
        "CAP 3 AI": "3484",
        "CAP 4 MH": "9822",
        "CAP 4 AI": "9823"
    }
    
    for year, url in portals.items():
        print(f"\nChecking portal {year} ({url}):")
        for desc, menu_id in menu_ids.items():
            check_link(url, menu_id)
