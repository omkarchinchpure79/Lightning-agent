import pdfplumber
import sys

def examine(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        print("=== PAGE 1 FULL TEXT ===")
        print(text)
        print("========================")

if __name__ == "__main__":
    examine("data/raw/pdfs/test_cutoff_9822.pdf")
