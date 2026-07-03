# MHT CET Cutoff PDF URL Patterns

Official CET Cell websites serve cutoff documents differently depending on the admission cycle year.

## Summary of Delivery Methods

| Year (Admission Cycle) | Portal Domain | Document Delivery Method |
|---|---|---|
| **2023** (A.Y. 2023-24) | `fe2024.mahacet.org` | Direct Static `.pdf` URLs under the `/2023/` folder |
| **2024** (A.Y. 2024-25) | `fe2024.mahacet.org` | base64-encoded PDF blobs embedded in `ViewPublicDocument.aspx?MenuId=XXXX` |
| **2025** (A.Y. 2025-26) | `fe2025.mahacet.org` | base64-encoded PDF blobs embedded in `ViewPublicDocument.aspx?MenuId=XXXX` |

---

## 2023 Direct PDF URLs (on `fe2024.mahacet.org`)

- **CAP Round I MH Cut Off**: `https://fe2024.mahacet.org/2023/2023ENGG_CAP1_CutOff.pdf`
- **CAP Round II MH Cut Off**: `https://fe2024.mahacet.org/2023/2023ENGG_CAP2_CutOff.pdf`
- **CAP Round III MH Cut Off**: `https://fe2024.mahacet.org/2023/2023ENGG_CAP3_CutOff.pdf`

*Note: All India (AI) cutoffs for 2023 are either included in these main MH PDFs or were not published under separate MenuIds.*

---

## 2024 & 2025 Base64 Document Pages

The documents are fetched from:
`https://{portal_domain}/ViewPublicDocument.aspx?MenuId={menu_id}`

The HTML response contains the PDF as a base64-encoded string inside a JavaScript call:
`LoadPublicDocument('base64_data')`

### Standard MenuId Mapping (Same for both 2024 and 2025)

| Document | MenuId |
|---|---|
| **CAP Round I MH Cut Off** | `2449` |
| **CAP Round I AI Cut Off** | `2450` |
| **CAP Round II MH Cut Off** | `3475` |
| **CAP Round II AI Cut Off** | `3476` |
| **CAP Round III MH Cut Off** | `3483` |
| **CAP Round III AI Cut Off** | `3484` |
| **CAP Round IV MH Cut Off** (2025 only) | `9822` |
| **CAP Round IV AI Cut Off** (2025 only) | `9823` |

---

## Download Script Plan

The script `scripts/download_all_pdfs.py` should implement:
1. Direct download for 2023 files.
2. Fetch + regex extract + base64 decode for 2024 and 2025 files.
3. Skip SSL verification (`ssl._create_unverified_context()`) for compatibility.
