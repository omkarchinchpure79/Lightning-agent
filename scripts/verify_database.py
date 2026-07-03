import sqlite3
import random
import pdfplumber
import os

DB_PATH = "db/edupath.db"
RAW_DIR = "data/raw/pdfs"

def run_verification():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("==================================================")
    print("      EDUPATH DATABASE SANITY & STRESS TEST       ")
    print("==================================================")

    # 1. Total Counts
    print("\n--- 1. Table Counts ---")
    cursor.execute("SELECT COUNT(*) FROM colleges;")
    col_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM branches;")
    br_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cutoffs;")
    cut_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM flagged_reviews;")
    flag_cnt = cursor.fetchone()[0]

    print(f"Colleges   : {col_cnt}")
    print(f"Branches   : {br_cnt}")
    print(f"Cutoffs    : {cut_cnt}")
    print(f"Flagged    : {flag_cnt}")

    # 2. Counts by Year and Round
    print("\n--- 2. Cutoffs by Year and CAP Round ---")
    cursor.execute("""
    SELECT year, round, is_all_india, COUNT(*) 
    FROM cutoffs 
    GROUP BY year, round, is_all_india 
    ORDER BY year, round, is_all_india;
    """)
    for y, r, ai, cnt in cursor.fetchall():
        q_type = "All India" if ai == 1 else "MH State"
        print(f"Year: {y} | Round: {r} | Quota: {q_type:<10} | Rows: {cnt}")

    # 3. Known Top Colleges verification (COEP, VJTI, PICT)
    print("\n--- 3. Spot Checking Top Colleges (Computer Engineering / IT) ---")
    top_colleges = {
        "3012": "VJTI Mumbai",
        "6006": "COEP Pune",
        "6271": "PICT Pune"
    }

    for code, name in top_colleges.items():
        print(f"\n>> {name} ({code}):")
        # Find branches matching Computer or Info Tech
        cursor.execute("""
        SELECT branch_code, branch_name 
        FROM branches 
        WHERE college_code = ? AND (branch_name LIKE '%Computer%' OR branch_name LIKE '%Information Technology%');
        """, (code,))
        branches = cursor.fetchall()
        if not branches:
            print("  No computer branches found!")
            continue

        for br_code, br_name in branches:
            print(f"  Branch: {br_name} ({br_code})")
            # Get GOPENS or GOPENH cutoff across 2023, 2024, 2025 for CAP 1
            cursor.execute("""
            SELECT year, seat_type, category, merit_no, percentile 
            FROM cutoffs 
            WHERE branch_code = ? AND round = 1 AND category IN ('GOPENS', 'GOPENH', 'AI')
            ORDER BY category, year;
            """, (br_code,))
            cutoffs = cursor.fetchall()
            for cy, cst, ccat, cmerit, cpct in cutoffs:
                print(f"    Year: {cy} | Category: {ccat:<7} | Seat: {cst:<25} | Merit: {cmerit:<6} | Percentile: {cpct:.7f}%")

    # 4. Spot Check 3 Random Cutoff Rows against Source PDF
    print("\n--- 4. Random Row Verification against Raw PDFs ---")
    cursor.execute("""
    SELECT cutoffs.year, cutoffs.round, cutoffs.seat_type, cutoffs.category, cutoffs.stage, 
           cutoffs.merit_no, cutoffs.percentile, cutoffs.is_all_india, cutoffs.exam_type,
           branches.branch_code, branches.branch_name, colleges.college_code, colleges.college_name
    FROM cutoffs
    JOIN branches ON cutoffs.branch_code = branches.branch_code
    JOIN colleges ON branches.college_code = colleges.college_code
    WHERE cutoffs.is_all_india = 0
    ORDER BY random() LIMIT 3;
    """)
    spot_rows = cursor.fetchall()

    for idx, row in enumerate(spot_rows):
        y, r, st, cat, stage, merit, pct, ai, exam, b_code, b_name, c_code, c_name = row
        print(f"\nSpot Check #{idx+1}:")
        print(f"  Year/Round : {y} CAP {r}")
        print(f"  College    : {c_name} ({c_code})")
        print(f"  Branch     : {b_name} ({b_code})")
        print(f"  Seat/Cat   : {st} / {cat} (Stage: {stage})")
        print(f"  DB Value   : Merit={merit}, Percentile={pct}%")

        # Verify in raw PDF
        pdf_filename = f"{y}_CAP{r}_MH.pdf"
        pdf_path = os.path.join(RAW_DIR, pdf_filename)
        if not os.path.exists(pdf_path):
            print(f"  [WARNING] PDF {pdf_path} not found for verification.")
            continue

        print(f"  Searching PDF: {pdf_filename} for choice code {b_code}...")
        found_pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if b_code in text:
                    found_pages.append(page_num + 1)

        if not found_pages:
            print(f"  [ERROR] Choice code {b_code} not found in PDF {pdf_filename}!")
        else:
            print(f"  Found choice code on pages: {found_pages}")
            # Print the context lines on the first found page
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[found_pages[0] - 1]
                text = page.extract_text()
                lines = text.split("\n")
                print("  PDF context around matches:")
                matched_lines = []
                for i, line in enumerate(lines):
                    if b_code in line:
                        # Print from previous college/branch heading down
                        start = max(0, i - 3)
                        end = min(len(lines), i + 10)
                        for k in range(start, end):
                            prefix = " -> " if k == i else "    "
                            print(f"{prefix}{lines[k]}")
                        break

    conn.close()

if __name__ == "__main__":
    run_verification()
