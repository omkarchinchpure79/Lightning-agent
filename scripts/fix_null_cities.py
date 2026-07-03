"""
fix_null_cities.py
Extracts city from college name strings for the 103 colleges with NULL city.
Strategy:
  1. Known manual overrides for brand colleges where name gives no city clue.
  2. Regex extraction from "...TownName" patterns at end of name.
  3. Keyword scan for known Maharashtra cities in the name.
Prints a dry-run summary, then writes to DB after confirmation.
"""

import re
import sqlite3
import sys

DB_PATH = "db/edupath.db"

# --- Hardcoded overrides: college_name substring -> city -----------------
# Used when the name itself doesn't contain a parseable location.
MANUAL_OVERRIDES = {
    "Sanjay Ghodawat":              "Kolhapur",
    "Sinhgad Institute of Technology": "Pune",
    "Svkm's Shri Bhagubhai Mafatlal": "Mumbai",
    "SVKM's Shri Bhagubhai Mafatlal": "Mumbai",
    "Thakur Shree DPS":             "Mumbai",
    "Karmayogi Institute":          "Osmanabad",
    "YASHWANTRAO BHONSALE":         "Sindhudurg",
    "Yadavrao Tasgaonkar College":  "Raigad",
    "Navsahyadri Education":        "Pune",
    "Navjeevan Education":          "Pune",
    "Samarth College":              "Nashik",
    "Sanjeevan Group":              "Kolhapur",
    "Sant Eknath College":          "Aurangabad",
    "VAMANRAO ITHAPE":              "Ahmednagar",
    "International Centre Of Excellence In Engineering and Management": "Aurangabad",
    "ICEEM":                        "Aurangabad",
    "JAMIA INSTITUTE":              "Akkalkuwa",
    "Devi Mahalaxmi College":       "Amravati",
    "Imperial College":             "Mumbai",
    "MES MUKUNDDAS":                "Akola",
    "Mangaldeep College":           "Jalgaon",
    "Pravin Rohidas Patil":         "Satara",
    "Ashok Institute of Engineering": "Sangamner",
    "CDS College of Engineering":   "Latur",
    "DNYANVILAS COLLEGE":           "Jalgaon",
    "Audyogik Shikshan Mandal's Nextgen": "Nashik",
    "Dr. V.K. Patil College":       "Kolhapur",
    "Amolak College":               "Beed",
    "NKSPT INSTITUTE":              "Kolhapur",
    "Mauli Group":                  "Buldhana",
    "MKD Institute":                "Nandurbar",
    "Eaglewood Polytechnic":        "Nashik",
    "P.G. College of Engineering":  "Nandurbar",
    "Shetkari Shikshan Prasarak":   "Ahmednagar",
    # Colleges with location in name that the generic extractor misreads
    "Everest Education Society":    "Nashik",       # Ohar, near Nashik
    "Vishwatmak Jangli Maharaj":    "Ahmednagar",   # Kokamthan, Ahmednagar
    "Ashokrao Mane Group":          "Kolhapur",     # Kagal, Kolhapur
    "Jaywant College":              "Sangli",       # Kille Macchindragad, Walva, Sangli
    "Rajendra Mane College":        "Ratnagiri",    # Ambav Deorukh, Ratnagiri
    "Anandrao Abitkar":             "Kolhapur",     # Pal, Kolhapur
    "Siddhivinayak Technical":      "Nashik",       # Shirasgon, Nile, Nashik
    "Shriram Institute Of Engineering": "Pune",     # Paniv, near Kopargaon but coded under Pune
    "Vishwaniketan":                "Raigad",       # Khalapur, Raigad
    "K. J.'s Educational Institut Trinity": "Pune", # Pisoli, Pune
    "K.J.'s Educational Institute's K.J.College": "Pune",  # Pisoli, Pune
    "Universal College of Engineering & Research": "Pune",  # Sasewadi, Pune
    "Vidya Niketan Institute of Engineering & Technology": "Pune",  # Lakhewadi, Pune
    "Shree Gajanan Maharaj Shikshan Prasarak":  "Pune",  # Dumbarwadi, Mawal, Pune
    "Krushi Jivan Vikas":           "Chandrapur",   # Ballarpur, Chandrapur
    "G.M.Vedak":                    "Raigad",       # Tala, Raigad
    "Paramhansa Ramkrishna":        "Buldhana",     # Chikhali, Buldhana
    "Konkan Gyanpeeth":             "Raigad",       # Karjat, Raigad
    "Leela Education Society":      "Raigad",       # Karjat, Raigad
    "Saraswati Education Society, Yadavrao Tasgaonkar": "Raigad",  # Karjat, Raigad
    "Koti Vidya":                   "Thane",        # Shahapur, Thane
    "Late Shri. Vishnu Waman Thakur": "Thane",      # Shirgaon, Vasai, Thane
    "Shree Shankar Narayan":        "Thane",        # Bhayander (E), Thane
    "Vidya Prasarini Sabha":        "Pune",         # Lonavala is in Pune district
    "Malwadi":                      "Ahmednagar",   # Bota/Malwadi is near Sangamner, Ahmednagar
    "Abhinav Education Society":    "Pune",         # Wadwadi is in Pune district
    "Amruta Vaishnavi":             "Nashik",       # Agaskhind, Tal. Sinnar, Nashik
    "Kedareshwar Gramin":           "Ahmednagar",   # Shevgaon, Ahmednagar
    "Hon. Shri. Babanrao Pachpute": "Ahmednagar",   # Kashti, Shrigonda, Ahmednagar
    "Bapurao Deshmukh":             "Wardha",       # Sevagram, Wardha
    "Kavi Kulguru":                 "Nagpur",       # Ramtek, Nagpur district
    "Karanjekar College":           "Nagpur",       # Sakoli, Bhandara (Nagpur division)
    "M.D. Yergude":                 "Chandrapur",   # Bhadrawati, Chandrapur
    "Haji Jamaluddin":              "Palghar",      # Boisar, Palghar
    "Jai Mahakali Shikshan Sanstha": "Nagpur",      # Sindhi(Meghe), near Nagpur
    "Shri Swami Samarth Institute": "Ahmednagar",   # Malwadi-Bota near Sangamner
    "Nagnathappa Halge":            "Beed",         # Parli, Beed
    "Fabtech Technical Campus":     "Solapur",      # Sangola, Solapur
    "Sahakar Maharshee":            "Solapur",      # Akluj, Solapur
    "Holy-Wood Academy":            "Kolhapur",     # Panhala, Kolhapur
    "Shree Tuljabhavani":           "Osmanabad",    # Tuljapur, Osmanabad
    "Mahatma Education Society's Pillai HOC": "Raigad",  # Khalapur, Raigad
    "Government College of Engineering & Research, Avasari": "Pune",  # Avasari Khurd, Pune
    "Jaihind College":              "Pune",         # Kuran, Junnar taluka, Pune district
    "Tatyasaheb Kore":              "Kolhapur",     # Yelur, near Warananagar, Kolhapur
    "Prof Ram Meghe":               "Amravati",     # Badnera railway jn. — Amravati twin city
    "Shri Sant Gajanan Maharaj":    "Buldhana",     # Shegaon, Buldhana
    "S.S.P.M.'s College":           "Sindhudurg",   # Kankavli, Sindhudurg
    "Shri. Jaykumar Rawal":         "Dhule",        # Dondaicha, Dhule district
}

# --- Known Maharashtra cities/towns for keyword scan --------------------
# Sorted longest-first so longer matches beat substrings (e.g. "Ahmednagar" before "Nagar")
KNOWN_CITIES = [
    "Chhatrapati Sambhajinagar", "Aurangabad", "Ahmednagar", "Nandurbar",
    "Sindhudurg", "Chandrapur", "Gadchiroli", "Buldhana", "Washim",
    "Yavatmal", "Bhandara", "Ratnagiri", "Sindhudurg",
    "Sangli", "Satara", "Kolhapur", "Solapur", "Nashik", "Jalgaon",
    "Dhule", "Nanded", "Latur", "Osmanabad", "Dharashiv",
    "Parbhani", "Hingoli", "Amravati", "Akola", "Wardha",
    "Gondia", "Nagpur", "Beed", "Raigad", "Palghar", "Thane",
    "Mumbai", "Pune",
    # Towns
    "Sangamner", "Pandharpur", "Ambejogai", "Malegaon", "Bhusawal",
    "Badlapur", "Panvel", "Karjat", "Jaysingpur", "Gadhinglaj",
    "Badnera", "Shegaon", "Tuljapur", "Kankavli", "Lonavala",
    "Akluj", "Chopda", "Dondaicha", "Faizpur", "Ramtek", "Pusad",
    "Akkalkuwa", "Shahada", "Parli", "Bhor", "Shahapur",
    "Bhayinder", "Bhayander", "Boisar", "Shirgaon",
]
KNOWN_CITIES_SORTED = sorted(KNOWN_CITIES, key=len, reverse=True)

# Tail tokens to skip (not city names)
NOISE_TOKENS = {
    "w", "e", "dist", "tal", "tq", "near", "at", "village", "road",
    "ohar", "poly", "kaman", "pal", "bota", "nile",
}


def _clean_token(tok):
    """Strip punctuation and normalize a name fragment."""
    return re.sub(r'[^a-z ]', '', tok.lower()).strip()


def extract_city_from_name(name):
    """Return a best-guess city for a college name, or None if unsure."""

    # 1. Manual overrides (substring match, case-insensitive)
    for frag, city in MANUAL_OVERRIDES.items():
        if frag.lower() in name.lower():
            return city

    # 2. Keyword scan across full name
    name_lower = name.lower()
    for city in KNOWN_CITIES_SORTED:
        # Whole-word match (surrounded by non-alpha or name boundary)
        pattern = r'(?<![a-z])' + re.escape(city.lower()) + r'(?![a-z])'
        if re.search(pattern, name_lower):
            return city

    # 3. Last comma-segment: "...College, Townname" or "...Campus, Townname, District"
    parts = [p.strip() for p in name.split(',')]
    if len(parts) >= 2:
        # Walk from last segment backwards; take the first non-noise token
        for seg in reversed(parts[1:]):
            seg_clean = _clean_token(seg)
            words = seg_clean.split()
            # Take last meaningful word
            candidate = next((w for w in reversed(words) if w not in NOISE_TOKENS and len(w) > 2), None)
            if candidate and len(candidate) >= 3:
                # Title-case it as a city
                city_guess = seg.strip().rstrip('.').strip()
                # Remove parenthetical suffixes like "(W)", "(E)"
                city_guess = re.sub(r'\s*\([^)]*\)', '', city_guess).strip()
                if city_guess and len(city_guess) >= 3:
                    return city_guess

    return None


def fix_cities(dry_run=True):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT college_name FROM colleges WHERE city IS NULL ORDER BY college_name")
    rows = cur.fetchall()
    print(f"Colleges with NULL city: {len(rows)}\n")

    updates = []
    skipped = []
    for (name,) in rows:
        city = extract_city_from_name(name)
        if city:
            updates.append((city, name))
        else:
            skipped.append(name)

    print(f"Resolved: {len(updates)}")
    print(f"Unresolved (will stay NULL): {len(skipped)}\n")

    print("--- Resolved ---")
    for city, name in updates:
        print(f"  {city:<30} <- {name[:65]}")

    if skipped:
        print("\n--- Unresolved (no city found) ---")
        for name in skipped:
            print(f"  {name[:80]}")

    if not dry_run:
        for city, name in updates:
            cur.execute(
                "UPDATE colleges SET city = ? WHERE college_name = ? AND city IS NULL",
                (city, name)
            )
        conn.commit()
        print(f"\nUpdated {cur.rowcount if len(updates)==1 else len(updates)} colleges.")
    else:
        print("\n[Dry run — pass --write to commit changes]")

    conn.close()
    return updates, skipped


if __name__ == "__main__":
    dry = "--write" not in sys.argv
    updates, skipped = fix_cities(dry_run=dry)
