import pdfplumber

def examine_coordinates():
    with pdfplumber.open("data/raw/pdfs/test_cutoff_9822.pdf") as pdf:
        page = pdf.pages[1] # Page 2
        words = page.extract_words()
        
        # Let's filter words that are in the vertical range of:
        # "0100246610 - Instrumentation Engineering"
        # Let's find where this text is
        target_y = None
        for w in words:
            if "0100246610" in w["text"]:
                target_y = w["top"]
                print(f"Found target code at y={target_y}")
                break
                
        if target_y is None:
            print("Could not find target college code on Page 2.")
            return
            
        # Get words in the range of y from target_y to target_y + 150
        section_words = [w for w in words if target_y <= w["top"] <= target_y + 120]
        
        # Group words by line (similar top coordinate, e.g. within 3 points)
        lines = {}
        for w in section_words:
            # Round top to group lines
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
            for w in line_words:
                print(f"  Word: '{w['text']}' at x=[{w['x0']:.2f}, {w['x1']:.2f}]")

if __name__ == "__main__":
    examine_coordinates()
