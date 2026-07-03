"""
Fix college_details and college_data_sources records corrupted by
Wikipedia false-positive matches during the scrape_all_colleges.py run.

Run AFTER the scrape completes. Each false positive is logged with:
  - db_code: canonical college code
  - wrong_wiki: the Wikipedia page incorrectly matched
  - sources_to_clear: source_type values whose data must be removed
  - fields_to_null: which college_details columns to set NULL

After clearing, the college is reset to status='pending' so the
fixed _name_matches() code picks it up cleanly on re-run.
"""
import sqlite3
import sys

DB_PATH = "db/edupath.db"

# (college_code, label, wrong_wiki_match, sources_to_clear, fields_to_null)
# sources_to_clear: 'wikipedia', 'official_website', or both
# fields_to_null: list of college_details columns to blank
FALSE_POSITIVES = [
    # 1. GCE Aurangabad (2008) matched GCE Amravati
    ("2008", "GCE Aurangabad", "Government College of Engineering, Amravati",
     ["wikipedia"], ["year_established", "website_url", "institution_type", "naac_grade"]),

    # 2. Dr. Rajendra Gode IT (1123) matched SGBAU university
    #    wikipedia set website_url=sgbau.ac.in, then official_website (sgbau.ac.in)
    #    wrote naac_grade + campus_area_acres — all wrong for this college
    ("1123", "Dr Rajendra Gode IT", "Sant Gadge Baba Amravati University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type", "naac_grade", "campus_area_acres"]),

    # 3. Prof Ram Meghe CE (1128) also matched SGBAU — same issue
    ("1128", "Prof Ram Meghe CE Badner", "Sant Gadge Baba Amravati University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type", "naac_grade", "campus_area_acres"]),

    # 4. Deogiri CE (2114) matched BAMU university
    ("2114", "Deogiri CE Aurangabad", "Dr. Babasaheb Ambedkar Marathwada University",
     ["wikipedia"], ["year_established", "institution_type"]),

    # 5. M.S. Bidve CE (2129) matched Latur city article
    ("2129", "MS Bidve CE Latur", "Latur (city article)",
     ["wikipedia"], ["year_established", "website_url"]),

    # 6. Peoples Education Society CE (2134) matched Maulana Azad College
    #    then official site maca.ac.in wrote year_established too
    ("2134", "Peoples Education CE", "Maulana Azad College of Arts Science Commerce",
     ["wikipedia", "official_website"], ["year_established", "website_url"]),

    # 7. MSPM Parbhani (2252) matched Parbhani city article
    ("2252", "MSPM Parbhani", "Parbhani (city article)",
     ["wikipedia"], ["year_established", "website_url"]),

    # 8. STMEI Sandipani (2522) matched Latur district article
    ("2522", "STMEI Sandipani", "Latur district article",
     ["wikipedia"], ["website_url"]),

    # 9. GCE Ratnagiri (3042) matched GCE Karad; official scraped gcekarad.ac.in
    ("3042", "GCE Ratnagiri", "Government College of Engineering, Karad",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 10. Bharati Vidyapeeth CE Navi Mumbai (3189) matched Bharati Vidyapeeth (university)
    #     then official bvuniversity.edu.in wrote year_established
    ("3189", "Bharati Vidyapeeth CE Navi Mumbai", "Bharati Vidyapeeth (university)",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 11. Agnel/FR C Rodrigues IT Vasai (3197) matched Fr Conceicao Rodrigues CE Bandra
    #     (two different colleges sharing the name "Rodrigues")
    ("3197", "Agnel FR C Rodrigues IT Vasai", "Fr. Conceicao Rodrigues College of Engg Bandra",
     ["wikipedia"], ["year_established", "institution_type", "naac_grade"]),

    # 12. Gharda IT Khed Ratnagiri (3216) matched "Keki Hormusji Gharda" (person article)
    #     year extracted from person's founded-company date
    ("3216", "Gharda IT Khed", "Keki Hormusji Gharda (person article)",
     ["wikipedia"], ["year_established"]),

    # 13. Shree LR Tiwari CE Mira Road (3423) matched Royal College of Science Arts Commerce
    #     then official royalcollegemiraroad.edu.in wrote naac_grade + has_sports
    ("3423", "Shree LR Tiwari CE Mira Road", "Royal College of Science Arts Commerce",
     ["wikipedia", "official_website"],
     ["website_url", "naac_grade", "has_sports"]),

    # 14. Laxminarayan IT Nagpur (4005) matched Laxminarayan Innovation Tech University
    #     (different institution — the university is unrelated to LIT Nagpur)
    #     official litu.edu.in scraped but nothing extracted (so only wikipedia source)
    ("4005", "Laxminarayan IT Nagpur", "Laxminarayan Innovation Technological University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "naac_grade"]),

    # 15. GCE Nagpur (4025) matched Government Polytechnic Nagpur
    #     Official gcoen.ac.in correctly wrote naac_grade + hostels — keep those
    ("4025", "GCE Nagpur", "Government Polytechnic, Nagpur",
     ["wikipedia"], ["year_established", "institution_type"]),

    # 16. Bapurao Deshmukh CE Sevagram (4118) matched Wardha (city article)
    ("4118", "Bapurao Deshmukh CE Sevagram", "Wardha (city article)",
     ["wikipedia"], ["year_established"]),

    # 17. GH Raisoni Institute of Engineering Nagpur (4142) matched GH Raisoni
    #     COLLEGE of Engineering (a different campus). Wrote year + website URL
    #     for the other campus. Official ghrce.raisoni.net scraped but nothing extracted.
    ("4142", "GH Raisoni IE Nagpur 2nd campus", "G. H. Raisoni College of Engineering Nagpur (main campus)",
     ["wikipedia"], ["year_established", "website_url"]),

    # 18. KDK College of Engineering Nagpur (4147) matched VNIT Nagpur
    #     Wikipedia wrote year (1960/VNIT founding), website (vnit.ac.in), institution_type.
    #     Then official vnit.ac.in also wrote year_established (VNIT's year) — all wrong.
    ("4147", "KDK CE Nagpur", "Visvesvaraya National Institute of Technology, Nagpur",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 19. Rajiv Gandhi CE&T Chandrapur (4163) matched list article
    #     "List of institutions of higher education in Maharashtra" — extracted
    #     year_established from some other college mentioned inline in the list.
    ("4163", "Rajiv Gandhi CE&T Chandrapur", "List of institutions of higher education in Maharashtra",
     ["wikipedia"], ["year_established"]),

    # 20. UICT North Maharashtra University Jalgaon (5003) matched SPPU
    #     Wrote SPPU founding year (1949), website unipune.ac.in, institution_type.
    #     Official unipune.ac.in scraped but nothing extracted.
    ("5003", "UICT NMU Jalgaon", "Savitribai Phule Pune University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 21. GCE Jalgaon (5004) matched Government Polytechnic Jalgaon
    ("5004", "GCE Jalgaon", "Government Polytechnic Jalgaon",
     ["wikipedia"], ["year_established"]),

    # 22. Khandesh CE Jalgaon (5106) matched Mahatma Phule Krishi Vidyapeeth
    #     (an agricultural university in Rahuri — completely different domain)
    ("5106", "Khandesh CE Jalgaon", "Mahatma Phule Krishi Vidyapeeth (agricultural university)",
     ["wikipedia"], ["year_established", "institution_type"]),

    # 23. CE&T North Maharashtra Knowledge Campus Jalgaon (5396) matched SPPU again
    #     Same as 5003 — SPPU wrote 3 fields. Official unipune.ac.in nothing.
    ("5396", "CE&T NMU Knowledge Campus Jalgaon", "Savitribai Phule Pune University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 24. Jawahar Education Society IT Nashik (5401) matched list article
    #     "List of institutions of higher education in Maharashtra" — extracted year
    ("5401", "Jawahar IT Nashik", "List of institutions of higher education in Maharashtra",
     ["wikipedia"], ["year_established"]),

    # 25. SVKM's IT Dhule (5449) matched SVKM's NMIMS (the Mumbai HQ of the parent trust)
    #     Wikipedia wrote year (1981), website (nmims.edu), institution_type.
    #     Then official nmims.edu wrote naac_grade (NMIMS's grade, not Dhule campus grade).
    ("5449", "SVKM IT Dhule", "SVKM's NMIMS (Mumbai main campus)",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type", "naac_grade"]),

    # 26. Department of Technology, Shivaji University Kolhapur (6028) matched SPPU
    ("6028", "Dept of Tech Shivaji Univ Kolhapur", "Savitribai Phule Pune University",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 27. GCE Kolhapur (6036) matched GCE Karad (different college/city)
    #     Official gcekarad.ac.in scraped but nothing extracted.
    ("6036", "GCE Kolhapur", "Government College of Engineering, Karad",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 28. MIT Academy of Engineering Alandi Pune (6146) matched MIT Group of Institutions
    #     (the parent trust; year is group's founding ~1983, not this newer campus)
    ("6146", "MIT Academy of Engineering Alandi", "MIT Group of Institutions",
     ["wikipedia"], ["year_established"]),

    # 29. Balasaheb Mane Shikshan Prasarak Mandal's CE Kolhapur (6217) matched
    #     Peth Vadgaon (a village in Kolhapur district)
    ("6217", "Balasaheb Mane CE Kolhapur", "Peth Vadgaon (village article)",
     ["wikipedia"], ["year_established"]),

    # 30. DY Patil CE&T Kolhapur (6250) matched Kolhapur district article
    #     Wrote website_url = kolhapur district government website. Official nothing.
    ("6250", "DY Patil CE&T Kolhapur", "Kolhapur district (government website)",
     ["wikipedia"], ["website_url"]),

    # 31. Karmaveer Bhaurao Patil CE Satara (6270) matched Satara (city)
    #     Wrote website_url = sataranp.in (Satara Nagarparishad). Official nothing.
    ("6270", "Karmaveer CE Satara", "Satara (city article)",
     ["wikipedia"], ["website_url"]),

    # 32. MKSSS Cummins CE for Women Pune (6276) matched MKSSS (the parent trust)
    #     Trust was founded 1896; college established 1991 — wrong year_established.
    ("6276", "MKSSS Cummins CE for Women Pune", "Maharshi Karve Stree Shikshan Samstha (parent trust)",
     ["wikipedia"], ["year_established"]),

    # 33. Bharati Vidyapeeth CE Kolhapur (6288) matched Bharati Vidyapeeth University
    #     Wikipedia wrote 3 fields; then bvuniversity.edu.in also wrote year_established.
    ("6288", "Bharati Vidyapeeth CE Kolhapur", "Bharati Vidyapeeth (parent university)",
     ["wikipedia", "official_website"],
     ["year_established", "website_url", "institution_type"]),

    # 34. Abhinav Education Society CE Pune (6318) matched Bhor (town in Pune district)
    ("6318", "Abhinav Education CE Pune", "Bhor (town article)",
     ["wikipedia"], ["year_established"]),

    # 35. Navsahyadri Education Society's Group of Institutions Pune (6632) also
    #     matched Bhor — same false positive
    ("6632", "Navsahyadri Group Pune", "Bhor (town article)",
     ["wikipedia"], ["year_established"]),

    # 36. Ajeenkya DY Patil School of Engineering Lohegaon Pune (6732) matched
    #     Lohagaon (a suburb/village near Pune airport)
    ("6732", "Ajeenkya DY Patil SE Lohegaon", "Lohagaon (village article)",
     ["wikipedia"], ["year_established"]),

    # 37. PK Technical Campus Pune (6768) matched College of Engineering, Pune (COEP)
    #     Got COEP's year (1854) and website (coeptech.ac.in). Official nothing.
    ("6768", "PK Technical Campus Pune", "College of Engineering, Pune (COEP's Wikipedia page)",
     ["wikipedia"], ["year_established", "website_url"]),
]


def clean(conn, code, label, wrong_wiki, sources, fields):
    cur = conn.cursor()

    # Verify the college exists in scrape_progress
    cur.execute("SELECT college_name FROM scrape_progress WHERE college_code=?", (code,))
    row = cur.fetchone()
    if not row:
        print(f"  SKIP {code} ({label}): not in scrape_progress")
        return

    print(f"\n  [{code}] {label}")
    print(f"    Wrong match: {wrong_wiki}")

    # Show what's currently in college_details
    if fields:
        placeholders = ", ".join(fields)
        cur.execute(f"SELECT {placeholders} FROM college_details WHERE college_code=?", (code,))
        vals = cur.fetchone()
        print(f"    Current values: {dict(zip(fields, vals or []))}")

    # Delete wrong college_data_sources entries
    for src in sources:
        cur.execute(
            "DELETE FROM college_data_sources WHERE college_code=? AND source_type=?",
            (code, src),
        )
        deleted = cur.rowcount
        print(f"    Deleted {deleted} college_data_sources rows (source_type={src})")

    # Null out the wrong field values
    for field in fields:
        cur.execute(
            f"UPDATE college_details SET {field}=NULL WHERE college_code=?",
            (code,),
        )

    if fields:
        print(f"    Nulled: {fields}")

    # Reset scrape_progress so the fixed matcher re-scrapes it
    cur.execute(
        """UPDATE scrape_progress
           SET status='pending', wikipedia_scraped=0, wikipedia_url=NULL,
               official_scraped=0, last_attempted=NULL
           WHERE college_code=?""",
        (code,),
    )
    print(f"    Reset scrape_progress -> pending")


def main():
    dry_run = "--dry-run" in sys.argv

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if dry_run:
        print("DRY RUN — no changes will be committed\n")

    print(f"Cleaning {len(FALSE_POSITIVES)} false-positive colleges...\n")

    for entry in FALSE_POSITIVES:
        code, label, wrong_wiki, sources, fields = entry
        clean(conn, code, label, wrong_wiki, sources, fields)

    if dry_run:
        conn.rollback()
        print("\nDry run complete — rolled back all changes.")
    else:
        conn.commit()
        print("\nAll changes committed.")

    # Summary after cleanup
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM scrape_progress GROUP BY status ORDER BY status")
    print("\nScrape progress after cleanup:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()
