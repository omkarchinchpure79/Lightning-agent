import pdfplumber

def check_ai_dupe():
    print("=== Checking AI dupe (0211301110) ===")
    pdf_path = "data/raw/pdfs/2024_CAP1_AI.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            if "0211301110" in text:
                print(f"Found 0211301110 on AI Page {idx+1}")
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if "0211301110" in line:
                        print(f"  {line}")

def check_mh_dupe():
    print("\n=== Checking MH dupe (303337290L) ===")
    pdf_path = "data/raw/pdfs/2023_CAP1_MH.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            if "303337290L" in text:
                print(f"Found 303337290L on MH Page {idx+1}")
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if "303337290L" in line:
                        print(f"  {line}")

if __name__ == "__main__":
    check_ai_dupe()
    check_mh_dupe()
