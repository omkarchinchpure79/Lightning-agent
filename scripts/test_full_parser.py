import pdfplumber
import re
import sys

def group_words_into_lines(words):
    lines = []
    for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
        placed = False
        for line in lines:
            if abs(line["top"] - w["top"]) < 3:
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

def parse_pdf(pdf_path, max_pages=10):
    print(f"Parsing PDF: {pdf_path} (max pages: {max_pages})")
    
    college_pattern = re.compile(r"^(\d{4,5})\s*-\s*(.*)")
    branch_pattern = re.compile(r"^(\d{8,10})\s*-\s*(.*)")
    
    current_college_code = None
    current_college_name = None
    current_branch_code = None
    current_branch_name = None
    current_seat_type = None
    current_headers = []
    
    pending_merit = None # Will store (stage_name, merit_map)
    records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        pages_to_parse = min(total_pages, max_pages)
        
        for page_idx in range(pages_to_parse):
            page = pdf.pages[page_idx]
            words = page.extract_words()
            lines = group_words_into_lines(words)
            
            print(f"\n--- Page {page_idx+1} (Lines: {len(lines)}) ---")
            
            for line_idx, line in enumerate(lines):
                text = line["text"].strip()
                
                # 1. College Header
                col_match = college_pattern.match(text)
                if col_match:
                    current_college_code = col_match.group(1)
                    current_college_name = col_match.group(2)
                    current_branch_code = None
                    current_branch_name = None
                    current_seat_type = None
                    current_headers = []
                    pending_merit = None
                    print(f"College: {current_college_code} - {current_college_name}")
                    continue
                    
                # 2. Branch Header
                br_match = branch_pattern.match(text)
                if br_match:
                    current_branch_code = br_match.group(1)
                    current_branch_name = br_match.group(2)
                    current_seat_type = None
                    current_headers = []
                    pending_merit = None
                    print(f"  Branch: {current_branch_code} - {current_branch_name}")
                    continue
                    
                # If we don't have a college or branch yet, skip general page headers
                if not current_college_code or not current_branch_code:
                    continue
                    
                # 3. Table Header Line (Starts with Stage)
                if text.startswith("Stage"):
                    current_headers = []
                    # Word 0 is 'Stage'
                    stage_word = line["words"][0]
                    # The rest are category headers
                    for w in line["words"][1:]:
                        current_headers.append({
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "center": (w["x0"] + w["x1"]) / 2
                        })
                    pending_merit = None
                    print(f"    Headers: {[h['text'] for h in current_headers]}")
                    continue
                    
                # 4. Check if it's a Seat Type line
                # Seat type lines usually describe the category of seats, e.g. "State Level" or contain "Seats Allotted"
                # They appear before the Stage headers.
                # Let's verify if this line is a seat type
                is_seat_type = False
                if "Seats Allotted" in text or text == "State Level" or text.endswith("Candidates"):
                    is_seat_type = True
                elif not text.startswith("Status:") and not text.startswith("Legends:") and not text.startswith("*") and not text.isdigit() and len(current_headers) == 0:
                    # If we don't have headers yet and it's not status/legends/page number, it's likely a seat type description
                    is_seat_type = True
                    
                if is_seat_type:
                    current_seat_type = text
                    current_headers = []
                    pending_merit = None
                    print(f"    Seat Type: {current_seat_type}")
                    continue
                    
                # 5. Skip legends, footer, etc.
                if text.startswith("Legends:") or text.startswith("*") or text.isdigit():
                    continue
                if text.startswith("Status:"):
                    continue
                    
                # 6. Wrapped Header processing
                # If we have headers and this line is NOT a value line (doesn't start with stage indicator)
                # and contains text that could be part of headers
                is_value_line = False
                first_word = line["words"][0]["text"]
                
                # Merit lines start with Roman numeral or stage like I, II, III, VII, I-Non, II-Non, etc.
                # or a percentile in parenthesis like (90.5)
                is_merit_line = False
                is_percentile_line = False
                
                if re.match(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X)(-Non)?$", first_word):
                    is_merit_line = True
                    is_value_line = True
                elif first_word.startswith("("):
                    is_percentile_line = True
                    is_value_line = True
                elif first_word in ["Defence", "PWD", "Orphan"] and pending_merit is not None:
                    # This is the second line of a split stage (e.g. PWD or Defence)
                    is_percentile_line = True
                    is_value_line = True
                
                if current_headers and not is_value_line:
                    # Let's check if the words in this line align with existing headers
                    # If so, they are wrapped headers (like the 'S' for 'DEFRSEBC')
                    aligned_words = 0
                    for w in line["words"]:
                        # Find closest header
                        closest_h = None
                        min_dist = 9999
                        w_center = (w["x0"] + w["x1"]) / 2
                        for h in current_headers:
                            dist = abs(w_center - h["center"])
                            if dist < min_dist:
                                min_dist = dist
                                closest_h = h
                        if min_dist < 25:
                            aligned_words += 1
                            closest_h["text"] += w["text"] # Append wrapped character
                            
                    if aligned_words > 0:
                        print(f"    [Merged Wrapped Header] New Headers: {[h['text'] for h in current_headers]}")
                        continue
                        
                # 7. Process Merit Line (Merit Numbers)
                if is_merit_line:
                    stage_name = first_word
                    merit_map = {}
                    # Remaining words should be numbers
                    for w in line["words"][1:]:
                        val = w["text"]
                        if val.isdigit():
                            # Find closest header
                            closest_h = None
                            min_dist = 9999
                            w_center = (w["x0"] + w["x1"]) / 2
                            for h in current_headers:
                                dist = abs(w_center - h["center"])
                                if dist < min_dist:
                                    min_dist = dist
                                    closest_h = h
                            if closest_h and min_dist < 25:
                                merit_map[closest_h["text"]] = int(val)
                    pending_merit = (stage_name, merit_map)
                    continue
                    
                # 8. Process Percentile Line
                if is_percentile_line:
                    stage_suffix = ""
                    percentile_words = []
                    
                    # If the line starts with Defence/PWD/Orphan, it is the second part of a split stage name
                    if first_word in ["Defence", "PWD", "Orphan"]:
                        stage_suffix = first_word
                        # The rest of the words are the percentiles
                        percentile_words = line["words"][1:]
                    else:
                        percentile_words = line["words"]
                        
                    if pending_merit is not None:
                        prev_stage_name, merit_map = pending_merit
                        
                        # Full stage name
                        full_stage_name = prev_stage_name
                        if stage_suffix:
                            full_stage_name = f"{prev_stage_name} {stage_suffix}"
                            
                        # Process percentiles
                        for w in percentile_words:
                            val = w["text"]
                            # Clean parenthesis
                            if val.startswith("(") and val.endswith(")"):
                                pct_str = val[1:-1]
                                try:
                                    pct = float(pct_str)
                                    
                                    # Find closest header
                                    closest_h = None
                                    min_dist = 9999
                                    w_center = (w["x0"] + w["x1"]) / 2
                                    for h in current_headers:
                                        dist = abs(w_center - h["center"])
                                        if dist < min_dist:
                                            min_dist = dist
                                            closest_h = h
                                    if closest_h and min_dist < 25:
                                        category = closest_h["text"]
                                        merit_no = merit_map.get(category)
                                        
                                        record = {
                                            "college_code": current_college_code,
                                            "college_name": current_college_name,
                                            "branch_code": current_branch_code,
                                            "branch_name": current_branch_name,
                                            "seat_type": current_seat_type,
                                            "category": category,
                                            "stage": full_stage_name,
                                            "merit_no": merit_no,
                                            "percentile": pct
                                        }
                                        records.append(record)
                                        print(f"      Record: {category} ({full_stage_name}) -> Merit: {merit_no}, Percentile: {pct}")
                                except ValueError:
                                    pass
                        pending_merit = None # Reset
                    else:
                        print("    WARNING: Percentile line found without pending merit line!")
                        
    print(f"\nParsing Complete. Total Records Extracted: {len(records)}")
    return records

if __name__ == "__main__":
    records = parse_pdf("data/raw/pdfs/test_cutoff_9822.pdf", max_pages=5)
