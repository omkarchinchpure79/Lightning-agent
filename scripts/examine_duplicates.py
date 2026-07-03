import sqlite3

def examine_dupes():
    conn = sqlite3.connect("db/edupath.db")
    cursor = conn.cursor()
    
    # Query duplicates for 303319110
    cursor.execute("""
    SELECT id, year, round, seat_type, category, stage, merit_no, percentile, branch_code, is_all_india
    FROM cutoffs
    WHERE branch_code = '303319110' AND category = 'GOPENS' AND year = 2023 AND round = 1;
    """)
    rows = cursor.fetchall()
    print("=== Duplicates for 303319110 ===")
    for r in rows:
        print(r)
        
    # Let's find how many duplicate combinations exist in total
    cursor.execute("""
    SELECT year, round, branch_code, seat_type, category, stage, COUNT(*)
    FROM cutoffs
    GROUP BY year, round, branch_code, seat_type, category, stage
    HAVING COUNT(*) > 1
    LIMIT 10;
    """)
    dupes_summary = cursor.fetchall()
    print("\n=== Top 10 duplicates summary ===")
    for d in dupes_summary:
        print(d)
        
    conn.close()

if __name__ == "__main__":
    examine_dupes()
