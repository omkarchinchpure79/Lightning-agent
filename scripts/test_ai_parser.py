import pdfplumber
import re
import sys

def group_words_into_lines(words):
    lines = []
    for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
        placed = False
        for line in lines:
            if abs(line["top"] - w["top"]) < 4.5:
                line["words"].append(w)
                placed = True
                break
        if not placed:
            lines.append({"top": w["top"], "words": [w]})
            
    lines.sort(key=lambda x: x["top"])
    for line in lines:
        line["words"].sort(key=lambda x: x["x0"])
        line["text"] = " ".join([w["text"] for w in line["words"]])
    return lines

def parse_ai_pdf(pdf_path, max_pages=3):
    print(f"Parsing AI PDF: {pdf_path} (max pages: {max_pages})")
    
    # We look for a line starting with an integer (Sr. No.), followed by All India Merit,
    # percentile in parenthesis, and choice code (10 digits)
    # Example: "1 15312 (86.6844102) 0110124210 ..."
    record_start_pattern = re.compile(r"^(\d+)\s+(\d+)\s+\(([^)]+)\)\s+(\d{9,10})")
    
    records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        pages_to_parse = min(total_pages, max_pages)
        
        for page_idx in range(pages_to_parse):
            page = pdf.pages[page_idx]
            words = page.extract_words()
            lines = group_words_into_lines(words)
            
            print(f"\n--- Page {page_idx+1} ---")
            
            current_record = None
            
            for line_idx, line in enumerate(lines):
                text = line["text"].strip()
                
                # Skip page headers, footers, page numbers, and column headers
                if any(x in text for x in ["Government of Maharashtra", "State Common Entrance Test Cell", "Cut Off List", "Academic Year", "Choice Code", "Cut Off Indicates", "Candidature Candidates", "Page "]) or text.isdigit():
                    continue
                    
                if text.startswith("1 ") or text.startswith("2 ") or text.startswith("3 "):
                    print(f"Debug line: '{text}'")
                    print("Regex match:", record_start_pattern.match(text))
                
                # Check if this is the start of a record
                match = record_start_pattern.match(text)
                if match:
                    # If we had a previous record, save it
                    if current_record:
                        records.append(current_record)
                        print(f"      Record: {current_record['choice_code']} -> Merit: {current_record['merit_no']}, Percentile: {current_record['percentile']}, Course: {current_record['course_name']}, Seat Type: {current_record['seat_type']}")
                    
                    sr_no = int(match.group(1))
                    merit_no = int(match.group(2))
                    percentile = float(match.group(3))
                    choice_code = match.group(4)
                    
                    # Remaining text on the line
                    remaining_text = text[match.end():].strip()
                    
                    # Parse college and course from the remaining text
                    # Format is usually: "college_code - college_name course_name category"
                    # E.g. "01101 - Shri Sant Gajanan Maharaj College of Engineering,Shegaon Computer Science and AI"
                    # Note: Category is always at the end (e.g. "AI")
                    
                    category = "AI"
                    if remaining_text.endswith(" AI"):
                        category = "AI"
                        remaining_text = remaining_text[:-3].strip()
                        
                    # Find college code and split
                    college_code = choice_code[:5]
                    college_name = ""
                    course_name = ""
                    
                    col_code_match = re.search(rf"{college_code}\s*-\s*", remaining_text)
                    if col_code_match:
                        # Extract college name and course name
                        parts = remaining_text.split(col_code_match.group(0), 1)
                        # parts[0] is usually empty or Choice Code repeated, parts[1] is college_name + course_name
                        college_and_course = parts[1]
                        
                        # Let's split by course name keywords or horizontal spacing
                        # Since pdfplumber parses left-to-right, college name is on the left (x < 500) and course name is on the right (x > 500)
                        # Let's check the words of the line
                        college_words = []
                        course_words = []
                        exam_words = []
                        seat_words = []
                        category_words = []
                        
                        for w in line["words"]:
                            w_center = (w["x0"] + w["x1"]) / 2
                            if w_center > 230:
                                if w_center < 530:
                                    college_words.append(w["text"])
                                elif w_center < 650:
                                    course_words.append(w["text"])
                                elif w_center < 700:
                                    exam_words.append(w["text"])
                                elif w_center < 780:
                                    seat_words.append(w["text"])
                                else:
                                    category_words.append(w["text"])
                                    
                        college_full = " ".join(college_words)
                        if college_full.startswith(f"{college_code} -"):
                            college_full = college_full[len(college_code)+3:].strip()
                        elif college_full.startswith("-"):
                            college_full = college_full[1:].strip()
                            
                        college_name = college_full
                        course_name = " ".join(course_words)
                        exam_type = " ".join(exam_words) if exam_words else "JEE"
                        seat_type = " ".join(seat_words) if seat_words else "AI to AI"
                        category = " ".join(category_words) if category_words else "AI"
                    else:
                        college_name = "Unknown College"
                        course_name = remaining_text
                        exam_type = "JEE"
                        seat_type = "AI to AI"
                        category = "AI"
                        
                    current_record = {
                        "sr_no": sr_no,
                        "merit_no": merit_no,
                        "percentile": percentile,
                        "choice_code": choice_code,
                        "college_code": college_code,
                        "college_name": college_name,
                        "course_name": course_name,
                        "category": category,
                        "exam_type": exam_type,
                        "seat_type": seat_type,
                        "stage": "I"
                    }
                    continue
                    
                # If this is not a record start line but we have an active record
                if current_record:
                    # Let's bin any wrapped words based on their x-coordinate
                    course_wrap_words = []
                    exam_wrap_words = []
                    seat_wrap_words = []
                    category_wrap_words = []
                    
                    for w in line["words"]:
                        w_center = (w["x0"] + w["x1"]) / 2
                        if 530 <= w_center < 650:
                            course_wrap_words.append(w["text"])
                        elif 650 <= w_center < 700:
                            exam_wrap_words.append(w["text"])
                        elif 700 <= w_center < 780:
                            seat_wrap_words.append(w["text"])
                        elif w_center >= 780:
                            category_wrap_words.append(w["text"])
                            
                    if course_wrap_words:
                        current_record["course_name"] = (current_record["course_name"] + " " + " ".join(course_wrap_words)).strip()
                    if exam_wrap_words:
                        current_record["exam_type"] = (current_record["exam_type"] + " " + " ".join(exam_wrap_words)).strip()
                    if seat_wrap_words:
                        current_record["seat_type"] = (current_record["seat_type"] + " " + " ".join(seat_wrap_words)).strip()
                    if category_wrap_words:
                        current_record["category"] = (current_record["category"] + " " + " ".join(category_wrap_words)).strip()
                        
            # Save the last record of the page
            if current_record:
                records.append(current_record)
                print(f"      Record: {current_record['choice_code']} -> Merit: {current_record['merit_no']}, Percentile: {current_record['percentile']}, Course: {current_record['course_name']}, Seat Type: {current_record['seat_type']}")
                
    print(f"\nParsing Complete. Total Records Extracted: {len(records)}")
    return records

if __name__ == "__main__":
    parse_ai_pdf("data/raw/pdfs/2025_CAP1_AI.pdf", max_pages=2)
