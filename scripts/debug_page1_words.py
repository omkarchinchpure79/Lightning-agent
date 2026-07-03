import pdfplumber

def debug_words():
    pdf_path = "data/raw/pdfs/2025_CAP1_AI.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        print("Total words on Page 1:", len(words))
        
        # Print words that are vertically close to 142.75
        for w in words:
            if abs(w["top"] - 142.75) < 5:
                print(f"Word: '{w['text']}' at x=[{w['x0']:.2f}, {w['x1']:.2f}], top={w['top']:.2f}")

if __name__ == "__main__":
    debug_words()
