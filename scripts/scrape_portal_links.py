import urllib.request
import re
import ssl

def scrape_homepage(year_url):
    print(f"Scraping homepage: {year_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        # Create unverified SSL context
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(year_url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        print(f"Fetched HTML. Length: {len(html)}")
        
        # Look for links containing ViewPublicDocument.aspx?MenuId=XXXX
        # e.g., href="ViewPublicDocument.aspx?MenuId=9822"
        pattern = r'href=["\'](?:[^"\']*ViewPublicDocument\.aspx\?MenuId=(\d+)[^"\']*)["\']([^>]*?>.*?</a>)'
        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        
        print(f"Found {len(matches)} links to ViewPublicDocument.aspx:")
        
        cutoff_links = []
        for menu_id, anchor_html in matches:
            # Clean anchor tag text
            text = re.sub(r'<[^>]+>', '', anchor_html).strip()
            # Clean up whitespace
            text = " ".join(text.split())
            if not text:
                text = "[Empty Text]"
            
            # Print if it contains interesting keywords
            keywords = ["cutoff", "cut off", "cut-off", "round", "cap", "merit", "mh", "ai", "all india", "maharashtra"]
            is_interesting = any(kw in text.lower() for kw in keywords)
            
            cutoff_links.append((menu_id, text, is_interesting))
            
        for menu_id, text, is_interesting in cutoff_links:
            if is_interesting:
                print(f"  MenuId={menu_id} -> '{text}'")
            else:
                # print(f"  (Other) MenuId={menu_id} -> '{text}'")
                pass
                
        return cutoff_links
    except Exception as e:
        print("ERROR:", str(e))
        return []

if __name__ == "__main__":
    print("=== 2025 PORTAL ===")
    scrape_homepage("https://fe2025.mahacet.org/")
    
    print("\n=== 2024 PORTAL ===")
    scrape_homepage("https://fe2024.mahacet.org/")
    
    print("\n=== 2023 PORTAL ===")
    scrape_homepage("https://fe2023.mahacet.org/")
    
    print("\n=== 2026 PORTAL ===")
    scrape_homepage("https://fe2026.mahacet.org/")
