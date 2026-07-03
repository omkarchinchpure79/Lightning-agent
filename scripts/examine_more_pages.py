import pdfplumber

def examine_more():
    with pdfplumber.open("data/raw/pdfs/test_cutoff_9822.pdf") as pdf:
        found_hu = 0
        found_stages = 0
        
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split("\n")
            
            # Check for Home University and print the context
            if "Home University" in text and found_hu < 3:
                print(f"=== Page {page_num+1} (Home University Context) ===")
                for i, line in enumerate(lines):
                    if "Home University" in line or "Other than Home University" in line:
                        start = max(0, i-2)
                        end = min(len(lines), i+8)
                        for idx in range(start, end):
                            print(f"{idx+1:02d}: {lines[idx]}")
                        print("--------------------------------")
                found_hu += 1
                
            # Check for multiple stage lines (e.g. Stage I, Stage II)
            stage_lines = [l for l in lines if l.strip().startswith("I ") or l.strip().startswith("II ") or l.strip().startswith("III ")]
            if len(stage_lines) > 1 and found_stages < 3:
                print(f"=== Page {page_num+1} (Multiple Stages Context) ===")
                for i, line in enumerate(lines):
                    if line.strip().startswith("Stage"):
                        start = max(0, i-1)
                        end = min(len(lines), i+10)
                        for idx in range(start, end):
                            print(f"{idx+1:02d}: {lines[idx]}")
                        print("--------------------------------")
                found_stages += 1
                
            if found_hu >= 3 and found_stages >= 3:
                break

if __name__ == "__main__":
    examine_more()
