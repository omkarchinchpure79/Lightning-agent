import os
import sys

def test_pdf_parsing(pdf_path):
    print(f"Testing PDF parsing on: {pdf_path}")
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file does not exist at {pdf_path}")
        return False
        
    try:
        import pdfplumber
        print("pdfplumber imported successfully.")
    except ImportError:
        print("pdfplumber is NOT installed. Trying to install it...")
        # We can try to import it, but let's just print a message and exit so we know we need to install it.
        return False

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"Total pages in PDF: {total_pages}")
            
            if total_pages > 0:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                print("\n--- FIRST PAGE TEXT SNIPPET ---")
                if text:
                    lines = text.split("\n")
                    for i, line in enumerate(lines[:30]):
                        print(f"{i+1:02d}: {line}")
                else:
                    print("[No text extracted from first page]")
                print("--------------------------------\n")
            
        return True
    except Exception as e:
        print("ERROR: Failed to parse PDF using pdfplumber:", str(e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    pdf_path = "data/raw/pdfs/test_cutoff_9822.pdf"
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    success = test_pdf_parsing(pdf_path)
    sys.exit(0 if success else 1)
