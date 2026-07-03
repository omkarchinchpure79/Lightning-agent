import pdfplumber

def examine_ai_coordinates():
    pdf_path = "data/raw/pdfs/2025_CAP1_AI.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        
        # Group words by line (similar top coordinate, e.g. within 3 points)
        lines = {}
        for w in words:
            found_line = False
            for top in lines:
                if abs(w["top"] - top) < 3:
                    lines[top].append(w)
                    found_line = True
                    break
            if not found_line:
                lines[w["top"]] = [w]
                
        # Sort lines by top coordinate
        sorted_tops = sorted(lines.keys())
        for top in sorted_tops:
            line_words = sorted(lines[top], key=lambda x: x["x0"])
            line_text = " ".join([w["text"] for w in line_words])
            print(f"y={top:6.2f}: {line_text}")
            # If the line contains "15312"
            if "15312" in line_text:
                for w in line_words:
                    print(f"  Word: '{w['text']}' at x=[{w['x0']:.2f}, {w['x1']:.2f}]")

if __name__ == "__main__":
    examine_ai_coordinates()
