"""
backfill_descriptions.py — Generate AI descriptions for all colleges in batches.

Rate-limited to 1 college every 2 seconds to avoid burning API budget.
Skips colleges that already have a description cached.

Usage:
    python scripts/backfill_descriptions.py [--limit N] [--force] [--dry-run]

Options:
    --limit N    Process at most N colleges (default: all)
    --force      Regenerate even if a description already exists
    --dry-run    Print colleges that would be processed without calling Claude
"""
import argparse
import os
import sys
import time
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, ROOT)

DB_PATH = os.path.join(ROOT, "db", "edupath.db")


def _load_dotenv():
    """Load KEY=value pairs from ROOT/.env into os.environ (no extra deps needed)."""
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS college_descriptions (
            college_code         TEXT PRIMARY KEY,
            description          TEXT NOT NULL,
            generated_at         TEXT NOT NULL DEFAULT (datetime('now')),
            edited_by_counselor  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()


def get_colleges(conn, limit, force):
    if force:
        sql = "SELECT college_code, college_name FROM colleges ORDER BY score DESC NULLS LAST"
    else:
        sql = """
            SELECT c.college_code, c.college_name
            FROM colleges c
            LEFT JOIN college_descriptions d ON d.college_code = c.college_code
            WHERE d.college_code IS NULL
            ORDER BY c.score DESC NULLS LAST
        """
    rows = conn.execute(sql).fetchall()
    # De-duplicate by name (prefer 5-digit code)
    seen = {}
    for r in rows:
        name = r["college_name"]
        code = r["college_code"]
        if name not in seen or len(code) > len(seen[name]):
            seen[name] = code
    unique = [(code, name) for name, code in seen.items()]
    if limit:
        unique = unique[:limit]
    return unique


def build_prompt(profile: dict) -> str:
    name = profile.get("college_name", "this college")
    identity = profile.get("identity", {})
    acc = profile.get("accreditation", {})
    loc = profile.get("location", {})
    place = profile.get("placements", {})

    naac = acc.get("naac_grade") or "N/A"
    nirf = f"#{acc.get('nirf_rank')}" if acc.get("nirf_rank") else "not ranked"
    place_pct = f"{place.get('placement_pct')}%" if place.get("placement_pct") is not None else "data unavailable"
    avg_pkg = f"{place.get('avg_package_lpa')} LPA" if place.get("avg_package_lpa") is not None else ""
    recruiters = place.get("top_recruiters") or ""
    inst_type = identity.get("institution_type") or ""
    district = loc.get("district") or ""
    year_est = identity.get("year_established") or ""
    university = loc.get("affiliated_university") or ""

    return f"""Write a friendly, warm description of {name} for a college counsellor's tool used in Maharashtra, India.

College facts:
- Type: {inst_type}
- Location: {district}, Maharashtra
- Affiliated to: {university}
- Established: {year_est}
- NAAC grade: {naac}
- NIRF rank: {nirf}
- Placement rate: {place_pct}  {f'· Avg package: {avg_pkg}' if avg_pkg else ''}
- Top recruiters: {recruiters if recruiters else 'not available'}

Write 3–4 sentences covering:
1. 💡 What the college is known for and its strengths
2. 👥 Which type of student it's best suited for
3. 🌟 What makes it unique (location, culture, infrastructure, programs)
4. 🎯 Key stats: NAAC, NIRF, placement % and one standout recruiter if known

Rules:
- Use emojis as bullet markers (💡 👥 🌟 🎯) — one per line
- Friendly, encouraging tone — not corporate brochure language
- Under 200 words
- If data is unavailable for a point, skip that point rather than saying "data unavailable"
- Do NOT invent stats; only use the facts provided above"""


def main():
    parser = argparse.ArgumentParser(description="Backfill AI descriptions for colleges")
    parser.add_argument("--limit", type=int, default=0, help="Max colleges to process (0=all)")
    parser.add_argument("--force", action="store_true", help="Regenerate existing descriptions")
    parser.add_argument("--dry-run", action="store_true", help="Print list without calling Claude")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        sys.exit("ANTHROPIC_API_KEY not set. Export it before running.")

    import engine_adapter as ea  # noqa: imported here so sys.path is set first
    import anthropic

    conn = get_conn()
    ensure_table(conn)

    colleges = get_colleges(conn, args.limit or None, args.force)
    total = len(colleges)
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing {total} college(s)...")

    if args.dry_run:
        for code, name in colleges:
            print(f"  {code}  {name}")
        conn.close()
        return

    client = anthropic.Anthropic(api_key=api_key)
    ok = 0
    failed = 0

    for i, (code, name) in enumerate(colleges, 1):
        print(f"[{i}/{total}] {code} — {name}", end=" ", flush=True)
        try:
            profile = ea.college_profile(code)
            if "error" in profile:
                print(f"SKIP (profile error: {profile['error']})")
                failed += 1
                continue

            prompt = build_prompt(profile)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            description = msg.content[0].text.strip()

            conn.execute(
                """
                INSERT INTO college_descriptions (college_code, description, generated_at, edited_by_counselor)
                VALUES (?, ?, datetime('now'), 0)
                ON CONFLICT(college_code) DO UPDATE SET
                    description  = excluded.description,
                    generated_at = excluded.generated_at,
                    edited_by_counselor = CASE WHEN edited_by_counselor = 1 THEN 1 ELSE 0 END
                """,
                (code, description),
            )
            conn.commit()
            print("✓")
            ok += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

        if i < total:
            time.sleep(2)  # 1 per 2 seconds — ~150/hr, safe within Tier-1 limits

    conn.close()
    print(f"\nDone. {ok} generated, {failed} failed.")


if __name__ == "__main__":
    main()
