import pdfplumber

def check_mh_page():
    pdf_path = "data/raw/pdfs/2023_CAP1_MH.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[233] # Page 234 is 233 in 0-index
        text = page.extract_text()
        print("=== MH Page 234 ===")
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "303337290L" in line:
                start = max(0, i-2)
                end = min(len(lines), i+15)
                for idx in range(start, end):
                    print(f"{idx+1:02d}: {lines[idx]}")
                print("---------------------")

if __name__ == "__main__":
    check_mh_page()
