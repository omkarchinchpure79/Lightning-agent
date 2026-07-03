import urllib.request
import ssl

def check_direct_url(url):
    print(f"Checking direct URL: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response:
            head = response.read(100)
            print(f"  [SUCCESS] Status: {response.status}, Length: {response.getheader('Content-Length')}")
            print(f"  First 20 bytes: {head[:20]}")
            if head.startswith(b"%PDF-"):
                print("  Starts with PDF header.")
            else:
                print("  WARNING: Does not start with %PDF-")
            return True
    except Exception as e:
        print(f"  [FAILED] Error: {str(e)}")
        return False

if __name__ == "__main__":
    check_direct_url("https://fe2024.mahacet.org/2023/2023ENGG_CAP1_CutOff.pdf")
    check_direct_url("https://fe2024.mahacet.org/2023/2023ENGG_CAP2_CutOff.pdf")
    check_direct_url("https://fe2024.mahacet.org/2023/2023ENGG_CAP3_CutOff.pdf")
