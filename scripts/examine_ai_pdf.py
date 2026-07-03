import pdfplumber

def examine_ai():
    pdf_path = "data/raw/pdfs/2025_CAP1_AI.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        print("=== ALL INDIA PDF PAGE 1 TEXT ===")
        print(text)
        print("=================================")

if __name__ == "__main__":
    examine_ai()
