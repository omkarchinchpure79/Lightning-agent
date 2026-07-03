import pdfplumber

def examine_page2():
    with pdfplumber.open("data/raw/pdfs/test_cutoff_9822.pdf") as pdf:
        page = pdf.pages[1] # Page 2
        words = page.extract_words()
        
        # Let's group all words on Page 2 by their top coordinate (line)
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
        for top in sorted_tops[:30]: # First 30 lines
            line_words = sorted(lines[top], key=lambda x: x["x0"])
            line_text = " ".join([w["text"] for w in line_words])
            print(f"y={top:6.2f}: {line_text}")
            # If the line contains "Stage" or "DEFRSEBC" or is very short (like "S")
            if "Stage" in line_text or "DEFRSEBC" in line_text or line_text.strip() == "S" or "14458" in line_text:
                for w in line_words:
                    print(f"  Word: '{w['text']}' at x=[{w['x0']:.2f}, {w['x1']:.2f}]")

if __name__ == "__main__":
    examine_page2()
