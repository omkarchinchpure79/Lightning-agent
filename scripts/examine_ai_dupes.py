import pdfplumber
import json
import re

def examine_dupe_in_pdf(pdf_path, choice_code):
    print(f"\nSearching for {choice_code} in {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            if choice_code in text:
                print(f"Found on page {page_idx + 1}:")
                lines = text.split("\n")
                for line in lines:
                    if choice_code in line:
                        print("  PDF Line:", line)

def examine_dupe_in_json(choice_code, year, round_num):
    print(f"\nSearching for {choice_code} in cutoffs.json for year={year}, round={round_num}...")
    with open("data/processed/cutoffs.json", "r") as f:
        data = json.load(f)
    matches = [r for r in data if r["branch_code"] == choice_code and r["year"] == year and r["round"] == round_num]
    for r in matches:
        print(f"  JSON Rec: {r['exam_type']} | {r['seat_type']} | {r['category']} | merit={r['merit_no']} | pct={r['percentile']}")

if __name__ == "__main__":
    # Dupe 1: 2024 CAP 3 AI, code 0512419110
    examine_dupe_in_pdf("data/raw/pdfs/2024_CAP3_AI.pdf", "0512419110")
    examine_dupe_in_json("0512419110", 2024, 3)

    # Dupe 2: 2025 CAP 4 AI, code 0112661210
    examine_dupe_in_pdf("data/raw/pdfs/2025_CAP4_AI.pdf", "0112661210")
    examine_dupe_in_json("0112661210", 2025, 4)

    # Dupe 3: 2025 CAP 4 AI, code 0525624610
    examine_dupe_in_pdf("data/raw/pdfs/2025_CAP4_AI.pdf", "0525624610")
    examine_dupe_in_json("0525624610", 2025, 4)

    # Dupe 4: 2025 CAP 4 AI, code 0621946110
    examine_dupe_in_pdf("data/raw/pdfs/2025_CAP4_AI.pdf", "0621946110")
    examine_dupe_in_json("0621946110", 2025, 4)
