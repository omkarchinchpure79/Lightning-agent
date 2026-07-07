<div align="center">

<h1>⚡ EduPath — Lightning Agent</h1>

<p><strong>A counsellor-facing decision-support tool for MHT CET CAP (Centralised Admission Process), Maharashtra.</strong></p>

<p>Predicts seat allotment probability from historical cutoff data, so counsellors can build smarter, safer preference lists for students during CAP rounds.</p>

</div>

<hr>

<h2>🧠 How the "Agent" actually works</h2>

<p>
This is <strong>not</strong> a wrapper around an external AI/ML API. The core of this project — seat prediction,
eligibility resolution, and preference-list ranking — is a <strong>local, deterministic, rule-based statistical engine</strong>
built directly on official historical cutoff data:
</p>

<ul>
  <li>Predictions use a <strong>carry-forward model</strong> (latest year's closing percentile), validated by backtesting
  against 27,000+ historical outcome groups — not a black-box model and not a call to any cloud ML service.</li>
  <li>Seat eligibility (Home / Other / State University) is resolved with explicit domain rules coded against each
  college's university mapping.</li>
  <li>Everything runs <strong>locally</strong> against a SQLite database (<code>db/edupath.db</code>) built from
  official CET Cell cutoff PDFs — no external inference API is required to use this tool.</li>
</ul>

<blockquote>
<p><strong>Transparency note:</strong> one optional, clearly-separated feature — auto-generating short descriptive
blurbs for college profile pages — calls the Anthropic API if an <code>ANTHROPIC_API_KEY</code> is supplied.
It is <em>not</em> used anywhere in the prediction, ranking, or eligibility logic, and the app works fully without it.</p>
</blockquote>

<h2>✨ Features</h2>

<ul>
  <li><strong>Seat allotment prediction</strong> — probability of clearing a given college/branch/category cutoff</li>
  <li><strong>Preference list builder</strong> — ranks colleges into SAFE / PROBABLE / REACH bands</li>
  <li><strong>CAP round strategy</strong> — lock-vs-wait guidance based on predicted Round 1 → Round 3 cutoff movement</li>
  <li><strong>College profiles</strong> — accreditation, fees by category, cutoff trends across years</li>
  <li><strong>Counsellor UI</strong> — a browser-based tool for building and exporting preference lists (print-friendly, no PDF dependency)</li>
</ul>

<h2>🛠️ Tech Stack</h2>

<table>
  <tr><td><strong>Language</strong></td><td>Python 3.14</td></tr>
  <tr><td><strong>Database</strong></td><td>SQLite (local file, no cloud DB)</td></tr>
  <tr><td><strong>PDF Parsing</strong></td><td>pdfplumber</td></tr>
  <tr><td><strong>UI</strong></td><td>Streamlit (counsellor tool) / Next.js web app</td></tr>
  <tr><td><strong>Data Source</strong></td><td>Official CET Cell cutoff PDFs (Maharashtra), 2023–2025</td></tr>
</table>

<h2>🚀 Getting Started</h2>

<pre><code>python scripts/download_all_pdfs.py          # Download official CET Cell cutoff PDFs
python scripts/parse_cutoffs.py          # Parse PDFs → structured, validated data
python scripts/load_db.py                # Load validated data into SQLite
python scripts/predict.py --percentile 88.0 --category GOPENS
streamlit run app/streamlit_app.py       # Launch the counsellor UI
</code></pre>

<h2>🔒 Data & Privacy</h2>

<ul>
  <li>Uses only <strong>official, publicly published</strong> cutoff data — no individual student records.</li>
  <li>No names, application IDs, or personal identifiers are stored, per India's DPDP Act.</li>
  <li>Every parsed row is validated against strict rules (percentile bounds, known category codes, known institute codes);
  anything that fails validation is quarantined for human review, never silently guessed.</li>
</ul>

<h2>⚠️ Disclaimer</h2>

<p>
This is an independent, unofficial project built to assist counsellors with preference planning.
It is <strong>not affiliated with, endorsed by, or officially connected to</strong> the Maharashtra CET Cell or DTE.
Predictions are estimates based on historical data and should be used as guidance alongside, not a replacement for,
official CAP information.
</p>
