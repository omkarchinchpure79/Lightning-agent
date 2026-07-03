import urllib.request
import re
import base64
import os
import sys

def test_extraction(menu_id, output_path):
    url = f"https://fe2025.mahacet.org/ViewPublicDocument.aspx?MenuId={menu_id}"
    print(f"Fetching: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        print("HTML fetched successfully. Length:", len(html))
        
        # Search for LoadPublicDocument('...')
        # We look for LoadPublicDocument('base64string')
        # We use a non-greedy or negated class to match everything inside single quotes
        pattern = r"LoadPublicDocument\s*\(\s*'([^']+)'\s*\)"
        matches = re.findall(pattern, html)
        
        if not matches:
            # Let's search case-insensitively or with double quotes just in case
            pattern = r"LoadPublicDocument\s*\(\s*\"([^\"]+)\"\s*\)"
            matches = re.findall(pattern, html)
            
        if not matches:
            print("ERROR: Could not find LoadPublicDocument call in HTML!")
            # Print a snippet of the script tags or search for other clues
            script_tags = re.findall(r"<script.*?>([\s\S]*?)</script>", html)
            print(f"Found {len(script_tags)} script tags in page.")
            for i, script in enumerate(script_tags):
                if "LoadPublicDocument" in script:
                    print(f"Script tag {i} contains 'LoadPublicDocument':")
                    print(script[:500] + "...")
            return False
            
        base64_str = matches[0].strip()
        print("Base64 string found! Length:", len(base64_str))
        print("First 50 chars:", base64_str[:50])
        print("Last 50 chars:", base64_str[-50:])
        
        # Decode base64
        try:
            pdf_data = base64.b64decode(base64_str)
            print("Successfully decoded base64. Byte size:", len(pdf_data))
        except Exception as e:
            print("ERROR: Failed to decode base64 string:", str(e))
            return False
            
        # Verify PDF header
        if pdf_data.startswith(b"%PDF-"):
            print("SUCCESS: Data starts with %PDF- header!")
        else:
            print("WARNING: Data does not start with %PDF- header. Starts with:", pdf_data[:20])
            
        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_data)
        print(f"PDF saved to: {output_path}")
        
        # Check file size
        saved_size = os.path.getsize(output_path)
        print(f"Saved file size on disk: {saved_size} bytes")
        
        return True
        
    except Exception as e:
        print("ERROR: An exception occurred during test:", str(e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    menu_id = "9822"  # CAP Round IV MH Cut Off for 2025
    if len(sys.argv) > 1:
        menu_id = sys.argv[1]
    
    output_pdf = f"data/raw/pdfs/test_cutoff_{menu_id}.pdf"
    success = test_extraction(menu_id, output_pdf)
    sys.exit(0 if success else 1)
