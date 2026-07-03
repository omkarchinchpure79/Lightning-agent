import pdfplumber
import re

def check_page_starts():
    college_pattern = re.compile(r"^\d{4,5}\s*-")
    branch_pattern = re.compile(r"^\d{8,10}\s*-")
    
    with pdfplumber.open("data/raw/pdfs/test_cutoff_9822.pdf") as pdf:
        anomalies = 0
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
            content_lines = []
            for line in lines:
                l = line.strip()
                if any(x in l for x in ["Government of Maharashtra", "State Common Entrance Test Cell", "Cut Off List", "Technical Courses", "Admissions A.Y.", "Legends:"]):
                    continue
                if l.isdigit(): # Page number
                    continue
                if not l:
                    continue
                content_lines.append(l)
            
            if not content_lines:
                continue
                
            first_line = content_lines[0]
            # Check if it starts with college or branch pattern
            is_college = college_pattern.match(first_line)
            is_branch = branch_pattern.match(first_line)
            
            if not is_college and not is_branch:
                anomalies += 1
                print(f"Anomaly on Page {page_idx+1}: First line is not college/branch:")
                for l in content_lines[:4]:
                    print(f"  {l}")
                print("-" * 50)
                if anomalies > 20:
                    print("Too many anomalies, stopping...")
                    break
        print(f"Total pages scanned: {len(pdf.pages)}. Total anomalies: {anomalies}")

if __name__ == "__main__":
    check_page_starts()
