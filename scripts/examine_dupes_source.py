import pdfplumber

def find_source():
    pdf_path = "data/raw/pdfs/2023_CAP1_MH.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            if "303319110" in text:
                print(f"=== Choice Code 303319110 found on Page {idx+1} ===")
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if "303319110" in line:
                        # Print surrounding 15 lines
                        start = max(0, i-2)
                        end = min(len(lines), i+15)
                        for idx_line in range(start, end):
                            print(f"{idx_line+1:02d}: {lines[idx_line]}")
                        print("-----------------------------------")

if __name__ == "__main__":
    find_source()
