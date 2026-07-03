import pdfplumber
import re
import os
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

# Directories
RAW_DIR = "data/raw/pdfs"
PROCESSED_DIR = "data/processed"
FLAGGED_DIR = "data/flagged"

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FLAGGED_DIR, exist_ok=True)

# ----------------- Helper Functions -----------------

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

# ----------------- Maharashtra (MH) Parser Chunk Worker -----------------

def parse_mh_pdf_chunk(pdf_path, year, round_num, start_page, end_page):
    college_pattern = re.compile(r"^(\d{4,5})\s*-\s*(.*)")
    branch_pattern = re.compile(r"^(\d{8,10}[A-Za-z]*)\s*-\s*(.*)")
    
    current_college_code = None
    current_college_name = None
    current_branch_code = None
    current_branch_name = None
    current_seat_type = None
    current_headers = []
    
    pending_merit = None
    records = []
    flagged = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Loop over the assigned page range
        for page_idx in range(start_page, min(end_page, len(pdf.pages))):
            page = pdf.pages[page_idx]
            words = page.extract_words()
            lines = group_words_into_lines(words)
            
            # Reset page-level headers/pending state
            current_headers = []
            pending_merit = None
            
            for line in lines:
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
                    continue
                    
                # 2. Branch Header
                br_match = branch_pattern.match(text)
                if br_match:
                    current_branch_code = br_match.group(1)
                    current_branch_name = br_match.group(2)
                    current_seat_type = None
                    current_headers = []
                    pending_merit = None
                    continue
                    
                if not current_college_code or not current_branch_code:
                    continue
                    
                # 3. Table Header Line (starts with "Stage" in 2023+ PDFs; in
                # pre-2023 captures, verified on 2019 Wayback data, the SAME
                # column label extracts as "egatS" — "Stage" character-reversed,
                # a pdfplumber quirk on that era's PDF text encoding, but in the
                # identical first-word position). Treat both as the header row.
                if text.startswith("Stage") or text.startswith("egatS"):
                    current_headers = []
                    for w in line["words"][1:]:
                        current_headers.append({
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "center": (w["x0"] + w["x1"]) / 2
                        })
                    pending_merit = None
                    continue

                # 4. Seat Type line
                is_seat_type = False
                if "Seats Allotted" in text or text == "State Level" or text.endswith("Candidates"):
                    is_seat_type = True
                elif not text.startswith("Status:") and not text.startswith("Legends:") and not text.startswith("*") and not text.isdigit() and len(current_headers) == 0:
                    is_seat_type = True
                    
                if is_seat_type:
                    current_seat_type = text
                    current_headers = []
                    pending_merit = None
                    continue
                    
                if text.startswith("Legends:") or text.startswith("*") or text.isdigit():
                    continue
                if text.startswith("Status:"):
                    continue
                    
                # 5. Wrapped Header processing
                is_value_line = False
                first_word = line["words"][0]["text"]
                
                is_merit_line = False
                is_percentile_line = False
                
                if re.match(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X)(-Non)?$", first_word):
                    is_merit_line = True
                    is_value_line = True
                elif first_word.startswith("("):
                    is_percentile_line = True
                    is_value_line = True
                elif first_word in ["Defence", "PWD", "Orphan"] and pending_merit is not None:
                    is_percentile_line = True
                    is_value_line = True
                
                if current_headers and not is_value_line:
                    aligned_words = 0
                    for w in line["words"]:
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
                            closest_h["text"] += w["text"]
                    if aligned_words > 0:
                        continue
                        
                # 6. Process Merit Line
                if is_merit_line:
                    stage_name = first_word
                    merit_map = {}
                    for w in line["words"][1:]:
                        val = w["text"]
                        if val.isdigit():
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
                    
                # 7. Process Percentile Line
                if is_percentile_line:
                    stage_suffix = ""
                    percentile_words = []
                    
                    if first_word in ["Defence", "PWD", "Orphan"]:
                        stage_suffix = first_word
                        percentile_words = line["words"][1:]
                    else:
                        percentile_words = line["words"]
                        
                    if pending_merit is not None:
                        prev_stage_name, merit_map = pending_merit
                        full_stage_name = prev_stage_name
                        if stage_suffix:
                            full_stage_name = f"{prev_stage_name} {stage_suffix}"
                            
                        for w in percentile_words:
                            val = w["text"]
                            if val.startswith("(") and val.endswith(")"):
                                pct_str = val[1:-1]
                                try:
                                    pct = float(pct_str)
                                    
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
                                        
                                        rec = {
                                            "year": year,
                                            "round": round_num,
                                            "college_code": current_college_code,
                                            "college_name": current_college_name,
                                            "branch_code": current_branch_code,
                                            "branch_name": current_branch_name,
                                            "seat_type": current_seat_type,
                                            "category": category,
                                            "stage": full_stage_name,
                                            "merit_no": merit_no,
                                            "percentile": pct,
                                            "is_all_india": 0,
                                            "exam_type": "MHT-CET"
                                        }
                                        
                                        validation_error = validate_record(rec)
                                        if validation_error:
                                            rec["reason"] = validation_error
                                            flagged.append(rec)
                                        else:
                                            records.append(rec)
                                            
                                except ValueError:
                                    pass
                        pending_merit = None
                        
    return records, flagged

# ----------------- All India (AI) Parser Chunk Worker -----------------

def parse_ai_pdf_chunk(pdf_path, year, round_num, start_page, end_page):
    record_start_pattern = re.compile(r"^(\d+)\s+(\d+)\s+\(([^)]+)\)\s+(\d{9,10})")
    
    records = []
    flagged = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in range(start_page, min(end_page, len(pdf.pages))):
            page = pdf.pages[page_idx]
            words = page.extract_words()
            lines = group_words_into_lines(words)
            
            current_record = None
            
            for line in lines:
                text = line["text"].strip()
                
                if any(x in text for x in ["Government of Maharashtra", "State Common Entrance Test Cell", "Cut Off List", "Academic Year", "Choice Code", "Cut Off Indicates", "Candidature Candidates", "Page "]) or text.isdigit():
                    continue
                    
                match = record_start_pattern.match(text)
                if match:
                    if current_record:
                        validation_error = validate_record(current_record)
                        if validation_error:
                            current_record["reason"] = validation_error
                            flagged.append(current_record)
                        else:
                            records.append(current_record)
                            
                    sr_no = int(match.group(1))
                    merit_no = int(match.group(2))
                    percentile = float(match.group(3))
                    choice_code = match.group(4)
                    
                    college_code = choice_code[:5]
                    
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
                    
                    current_record = {
                        "year": year,
                        "round": round_num,
                        "college_code": college_code,
                        "college_name": college_name,
                        "branch_code": choice_code,
                        "branch_name": course_name,
                        "seat_type": seat_type,
                        "category": category,
                        "stage": "I",
                        "merit_no": merit_no,
                        "percentile": percentile,
                        "is_all_india": 1,
                        "exam_type": exam_type
                    }
                    continue
                    
                if current_record:
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
                        current_record["branch_name"] = (current_record["branch_name"] + " " + " ".join(course_wrap_words)).strip()
                    if exam_wrap_words:
                        current_record["exam_type"] = (current_record["exam_type"] + " " + " ".join(exam_wrap_words)).strip()
                    if seat_wrap_words:
                        current_record["seat_type"] = (current_record["seat_type"] + " " + " ".join(seat_wrap_words)).strip()
                    if category_wrap_words:
                        current_record["category"] = (current_record["category"] + " " + " ".join(category_wrap_words)).strip()
                        
            if current_record:
                validation_error = validate_record(current_record)
                if validation_error:
                    current_record["reason"] = validation_error
                    flagged.append(current_record)
                else:
                    records.append(current_record)
                    
    return records, flagged

# ----------------- Worker Entry Point -----------------

def parse_pdf_chunk_worker(args):
    pdf_path, year, round_num, doc_type, start_page, end_page = args
    try:
        if doc_type == "MH":
            return parse_mh_pdf_chunk(pdf_path, year, round_num, start_page, end_page)
        elif doc_type == "AI":
            return parse_ai_pdf_chunk(pdf_path, year, round_num, start_page, end_page)
    except Exception as e:
        print(f"Error in worker processing {os.path.basename(pdf_path)} ({start_page}-{end_page}): {str(e)}")
        import traceback
        traceback.print_exc()
        return [], [{"year": year, "round": round_num, "college_code": "ERROR", "reason": f"Worker Exception: {str(e)}"}]

# ----------------- Validation Engine -----------------

# The full known-good CAP category vocabulary (105 codes verified against the
# live DB, roadmap audit 2026-07-03): General/Ladies + H/O/S suffix, the
# state-only specials, and Defence/PwD variants (optionally with the "R"
# reserved-quota infix, e.g. DEFRSEBCH, PWDRVJS). Rejects the rare (~3-in-105)
# single/double-letter garbage tokens ('H', 'MI', 'S') a table-alignment
# misfire can produce on dense category grids — e.g. 2019 CAP2's combined
# Home+PWD blocks fooled the seat-type/header heuristics into misattributing a
# whole concatenated category list to seat_type and leaving category as a
# stray leftover letter. Fail-closed: reject rather than guess which table
# block the row actually belonged to.
_VALID_CATEGORY_RE = re.compile(
    r"^([GL][A-Z0-9]{2,10}[HOS]"     # General/Ladies: GOPENH, LNT1S, GVJH, ...
    r"|EWS|TFWS|ORPHAN"               # state-only specials
    r"|DEFR?[A-Z0-9]+[HOS]"          # Defence: DEFOPENS, DEFRSEBCH, DEFOBCO, ...
    r"|PWDR?[A-Z0-9]+[HS])$"         # PwD: PWDOPENH, PWDRVJS, ...
)


def validate_record(rec):
    cat = rec.get("category")
    if not cat:
        return "Empty category code"
    if not _VALID_CATEGORY_RE.match(cat):
        return f"Category code doesn't match known CAP vocabulary: {cat!r}"

    pct = rec.get("percentile")
    if pct is None or pct < 0.0 or pct > 100.0:
        return f"Invalid percentile: {pct}"
        
    merit = rec.get("merit_no")
    if merit is not None and merit <= 0:
        return f"Invalid merit number: {merit}"
        
    cc = rec.get("college_code")
    if not cc or not cc.isdigit() or len(cc) not in [4, 5]:
        return f"Invalid college code: {cc}"
        
    bc = rec.get("branch_code")
    if not bc or not bc.isalnum() or len(bc) not in [8, 9, 10, 11, 12]:
        return f"Invalid branch/choice code: {bc}"
        
    if not rec.get("college_name"):
        return "Empty college name"
    if not rec.get("branch_name"):
        return "Empty branch name"
    if not rec.get("seat_type"):
        return "Empty seat type"
        
    return None

# ----------------- Main Execution -----------------

def main():
    print("EduPath Parallel Cutoff Parsing Engine starting...", flush=True)
    
    all_valid_records = []
    all_flagged_records = []
    
    if not os.path.exists(RAW_DIR):
        print(f"ERROR: Raw PDF directory {RAW_DIR} does not exist!", flush=True)
        sys.exit(1)
        
    files = [f for f in os.listdir(RAW_DIR) if f.endswith(".pdf")]
    print(f"Found {len(files)} files to parse in {RAW_DIR}.", flush=True)
    
    filename_pattern = re.compile(r"^(\d{4})_CAP(\d)_([A-Z]{2})\.pdf$")
    
    # We will build a list of tasks for the worker pool
    # Each task: (pdf_path, year, round_num, doc_type, start_page, end_page)
    tasks = []
    
    # We choose a chunk size (number of pages per worker task)
    # 150 pages is a good size: not too small (overhead) and not too large
    CHUNK_SIZE = 150
    
    print("Scanning PDF files to generate parallel page chunks...", flush=True)
    for f in sorted(files):
        match = filename_pattern.match(f)
        if not match:
            continue
            
        year = int(match.group(1))
        round_num = int(match.group(2))
        doc_type = match.group(3)
        pdf_path = os.path.join(RAW_DIR, f)

        # AI-quota (All India) PDFs from before 2023 use a column layout the
        # column-x-position parser (parse_ai_pdf_chunk) was never built against —
        # verified on 2019 Wayback data: parsing produces garbled college/branch
        # names (fields land in the wrong columns). AI rows never feed the
        # prediction model anyway (generate_predictions.py filters is_all_india=0),
        # so skip rather than risk silently loading wrong data. MH parsing for
        # these years IS verified correct (see module docstring / A1 audit).
        if doc_type == "AI" and year < 2023:
            print(f"  Skipping {f}: pre-2023 AI-quota layout not yet supported by "
                  f"the column-position parser (AI rows aren't used for predictions).")
            continue

        # Open PDF to get total pages
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
        print(f"  File {f}: {total_pages} pages total.")
        
        # Split pages into chunks
        for start in range(0, total_pages, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, total_pages)
            tasks.append((pdf_path, year, round_num, doc_type, start, end))
            
    print(f"Generated {len(tasks)} parallel tasks total.", flush=True)
    
    # Determine CPU workers
    num_workers = os.cpu_count() or 4
    print(f"Utilizing {num_workers} parallel CPU cores.", flush=True)
    
    # Execute in process pool
    completed_tasks = 0
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(parse_pdf_chunk_worker, t): t for t in tasks}
        
        for future in as_completed(futures):
            task = futures[future]
            pdf_name = os.path.basename(task[0])
            start_p, end_p = task[4], task[5]
            
            try:
                valid, flagged = future.result()
                all_valid_records.extend(valid)
                all_flagged_records.extend(flagged)
                
                completed_tasks += 1
                percent = (completed_tasks / len(tasks)) * 100
                print(f"[{percent:6.2f}%] Completed task: {pdf_name} (pages {start_p}-{end_p}). Extracted {len(valid)} valid rows.", flush=True)
            except Exception as e:
                print(f"CRITICAL ERROR in future for {pdf_name} (pages {start_p}-{end_p}): {str(e)}", flush=True)
                
    # Write output files
    valid_out = os.path.join(PROCESSED_DIR, "cutoffs.json")
    flagged_out = os.path.join(FLAGGED_DIR, "flagged_reviews.json")
    
    print("\nWriting processed records to files...", flush=True)
    with open(valid_out, "w") as f:
        json.dump(all_valid_records, f, indent=2)
        
    with open(flagged_out, "w") as f:
        json.dump(all_flagged_records, f, indent=2)
        
    print("\n" + "="*50)
    print("PARALLEL PARSING COMPLETE SUMMARY:")
    print(f"  Total Valid Records Extracted: {len(all_valid_records)}")
    print(f"  Total Flagged Records (Reviews Required): {len(all_flagged_records)}")
    print(f"  Valid records saved to: {valid_out}")
    print(f"  Flagged reviews saved to: {flagged_out}")
    print("="*50, flush=True)

if __name__ == "__main__":
    main()
