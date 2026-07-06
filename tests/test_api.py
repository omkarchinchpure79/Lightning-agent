"""
test_api.py — Integration tests for the EduPath FastAPI service.

Uses FastAPI's TestClient (httpx-backed, no live server needed).
All tests that create student records track their IDs and clean up in
tearDownClass, so the test DB stays tidy across repeated runs.

Existing 43 tests are never modified; this file only adds new tests.
"""
import os
import sys
import unittest

# Ensure project root is on path for `from api.main import app`.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient
from api.main import app
from api.db import init_tables

# init_tables() is idempotent (CREATE TABLE IF NOT EXISTS). Calling it here
# ensures the two API tables exist regardless of whether the TestClient
# enters the lifespan context manager before the first request.
init_tables()

_client = TestClient(app)

# Student/prediction routes require an authenticated counselor. Sign up (or log
# in, if a prior test run already created this account) a fixed test account
# once per test session and attach the token to every request the client makes.
_TEST_COUNSELOR = {"name": "Test Suite Counselor", "email": "__test_suite__@example.com", "password": "testsuitepass123"}
_signup_resp = _client.post("/api/auth/signup", json=_TEST_COUNSELOR)
if _signup_resp.status_code == 409:
    _signup_resp = _client.post("/api/auth/login", json={
        "email": _TEST_COUNSELOR["email"], "password": _TEST_COUNSELOR["password"],
    })
_TEST_TOKEN = _signup_resp.json()["token"]
_client.headers["Authorization"] = f"Bearer {_TEST_TOKEN}"

_STUDENT_BASE = {
    "name": "__test_api_student__",
    "percentile": 85.0,
    "category_base": "GOPEN",
    "home_district": "Pune",
}


class TestStudentCRUD(unittest.TestCase):
    _created: list[int] = []

    @classmethod
    def tearDownClass(cls):
        for sid in cls._created:
            _client.delete(f"/api/students/{sid}")
        cls._created.clear()

    def _create(self, **overrides) -> tuple[int, dict]:
        payload = {**_STUDENT_BASE, **overrides}
        resp = _client.post("/api/students", json=payload)
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self._created.append(data["id"])
        return data["id"], data

    def test_create_and_get_round_trip(self):
        sid, created = self._create(
            name="API Test — create",
            preferred_branches=["Computer", "Information Technology"],
        )
        resp = _client.get(f"/api/students/{sid}")
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertEqual(d["name"], "API Test — create")
        self.assertAlmostEqual(d["percentile"], 85.0)
        self.assertEqual(d["preferred_branches"], ["Computer", "Information Technology"])
        self.assertEqual(d["category_base"], "GOPEN")
        self.assertIsNotNone(d["created_at"])

    def test_patch_updates_field_and_preserves_others(self):
        sid, _ = self._create(name="API Test — patch")
        resp = _client.patch(f"/api/students/{sid}", json={"percentile": 91.5})
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertAlmostEqual(d["percentile"], 91.5)
        self.assertEqual(d["name"], "API Test — patch")   # unchanged
        self.assertEqual(d["category_base"], "GOPEN")     # unchanged
        self.assertIsNotNone(d["updated_at"])

    def test_list_students_returns_created(self):
        sid, _ = self._create(name="API Test — list")
        resp = _client.get("/api/students")
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.json()]
        self.assertIn(sid, ids)

    def test_delete_then_get_returns_404(self):
        sid, _ = self._create(name="API Test — delete")
        resp_del = _client.delete(f"/api/students/{sid}")
        self.assertEqual(resp_del.status_code, 204)
        resp_get = _client.get(f"/api/students/{sid}")
        self.assertEqual(resp_get.status_code, 404)
        # Already deleted; remove from cleanup list.
        if sid in self._created:
            self._created.remove(sid)

    def test_get_nonexistent_returns_404(self):
        resp = _client.get("/api/students/999999999")
        self.assertEqual(resp.status_code, 404)

    def test_create_rejects_unknown_base_category(self):
        # Fail-closed at write time: an invalid category must never reach the
        # DB (it would 400 on every later prediction call instead).
        payload = {**_STUDENT_BASE, "name": "API Test — bad category", "category_base": "OPEN"}
        resp = _client.post("/api/students", json=payload)
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("Unknown base category", resp.text)

    def test_create_normalises_lowercase_category(self):
        sid, created = self._create(name="API Test — lowercase cat", category_base="gopen")
        self.assertEqual(created["category_base"], "GOPEN")

    def test_patch_rejects_unknown_base_category(self):
        sid, _ = self._create(name="API Test — patch bad category")
        resp = _client.patch(f"/api/students/{sid}", json={"category_base": "NOTACAT"})
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("Unknown base category", resp.text)

    def test_patch_nonexistent_returns_404(self):
        resp = _client.patch("/api/students/999999999", json={"percentile": 70.0})
        self.assertEqual(resp.status_code, 404)


class TestDseStudentCRUD(unittest.TestCase):
    """Session 2 (Direct Second Year admission) — API-level checks."""
    _created: list[int] = []

    @classmethod
    def tearDownClass(cls):
        for sid in cls._created:
            _client.delete(f"/api/students/{sid}")
        cls._created.clear()

    def _create_dse(self, **overrides) -> tuple[int, dict]:
        payload = {"name": "API Test — DSE", "admission_type": "dse",
                   "diploma_pct": 88.0, "category_base": "GOPEN", **overrides}
        resp = _client.post("/api/students", json=payload)
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self._created.append(data["id"])
        return data["id"], data

    def test_create_dse_mirrors_diploma_pct_into_percentile(self):
        sid, created = self._create_dse(diploma_pct=91.25)
        self.assertEqual(created["admission_type"], "dse")
        self.assertAlmostEqual(created["diploma_pct"], 91.25)
        self.assertAlmostEqual(created["percentile"], 91.25)

    def test_create_dse_requires_diploma_pct(self):
        payload = {"name": "API Test — DSE no mark", "admission_type": "dse",
                   "category_base": "GOPEN"}
        resp = _client.post("/api/students", json=payload)
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_create_dse_rejects_tfws(self):
        payload = {"name": "API Test — DSE TFWS", "admission_type": "dse",
                   "diploma_pct": 80.0, "category_base": "TFWS"}
        resp = _client.post("/api/students", json=payload)
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("no seat quota in DSE", resp.text)

    def test_patch_to_dse_requires_diploma_pct(self):
        sid, _ = self._create({"name": "API Test — FE to DSE patch"})
        resp = _client.patch(f"/api/students/{sid}", json={"admission_type": "dse"})
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("diploma_pct", resp.text)

    def _create(self, payload: dict) -> tuple[int, dict]:
        full = {**_STUDENT_BASE, **payload}
        resp = _client.post("/api/students", json=full)
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self._created.append(data["id"])
        return data["id"], data

    def test_predictions_route_dse_students_to_dse_engine(self):
        sid, _ = self._create_dse(diploma_pct=88.0)
        resp = _client.post(f"/api/students/{sid}/predictions", json={"round_num": 1})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["admission_type"], "dse")
        total = data["counts"]["safe"] + data["counts"]["probable"] + data["counts"]["reach"]
        self.assertGreater(total, 0)

    def test_predictions_reject_round_3_for_dse(self):
        sid, _ = self._create_dse(diploma_pct=88.0)
        resp = _client.post(f"/api/students/{sid}/predictions", json={"round_num": 3})
        self.assertEqual(resp.status_code, 400, resp.text)


class TestShortlist(unittest.TestCase):
    _created: list[int] = []

    @classmethod
    def tearDownClass(cls):
        for sid in cls._created:
            _client.delete(f"/api/students/{sid}")
        cls._created.clear()

    def _create_student(self) -> int:
        resp = _client.post("/api/students", json={**_STUDENT_BASE, "name": "API Test — shortlist"})
        self.assertEqual(resp.status_code, 201)
        sid = resp.json()["id"]
        self._created.append(sid)
        return sid

    def test_save_and_retrieve_shortlist(self):
        sid = self._create_student()
        items = [
            {
                "canonical_code": "CODE::99999",
                "college_name": "Test College",
                "branch_name": "Computer Engineering",
                "band": "SAFE",
                "predicted_close": 92.5,
                "margin": 4.5,
                "confidence": "high",
                "category_used": "GOPENS",
                "seat_type": "State",
                "fee_text": "Rs 1,00,000",
            }
        ]
        resp = _client.post(f"/api/students/{sid}/shortlist", json={"items": items})
        self.assertEqual(resp.status_code, 200)

        resp2 = _client.get(f"/api/students/{sid}/shortlist")
        self.assertEqual(resp2.status_code, 200)
        d = resp2.json()
        self.assertEqual(d["student_id"], sid)
        self.assertEqual(len(d["items"]), 1)
        self.assertEqual(d["items"][0]["canonical_code"], "CODE::99999")
        self.assertEqual(d["items"][0]["band"], "SAFE")

    def test_shortlist_post_replaces_not_appends(self):
        sid = self._create_student()
        item_a = {"canonical_code": "CODE::11111", "college_name": "A"}
        item_b = {"canonical_code": "CODE::22222", "college_name": "B"}

        _client.post(f"/api/students/{sid}/shortlist", json={"items": [item_a]})
        _client.post(f"/api/students/{sid}/shortlist", json={"items": [item_b]})

        resp = _client.get(f"/api/students/{sid}/shortlist")
        items = resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["canonical_code"], "CODE::22222")

    def test_empty_shortlist_on_new_student(self):
        sid = self._create_student()
        resp = _client.get(f"/api/students/{sid}/shortlist")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])

    def test_shortlist_deleted_with_student(self):
        sid = self._create_student()
        _client.post(
            f"/api/students/{sid}/shortlist",
            json={"items": [{"canonical_code": "CODE::55555"}]},
        )
        _client.delete(f"/api/students/{sid}")
        if sid in self._created:
            self._created.remove(sid)
        # Student gone → shortlist endpoint also 404
        resp = _client.get(f"/api/students/{sid}/shortlist")
        self.assertEqual(resp.status_code, 404)


class TestPredictions(unittest.TestCase):
    _created: list[int] = []

    @classmethod
    def tearDownClass(cls):
        for sid in cls._created:
            _client.delete(f"/api/students/{sid}")
        cls._created.clear()

    def test_adhoc_prediction_returns_bands(self):
        payload = {
            "percentile": 88.0,
            "category_label": "General — Open",
            "home_district": "Pune",
            "branch_preferences": ["Computer"],
            "round_num": 1,
        }
        resp = _client.post("/api/predictions", json=payload)
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertIn("safe", d)
        self.assertIn("probable", d)
        self.assertIn("reach", d)
        self.assertIn("counts", d)

    def test_adhoc_prediction_unknown_category_returns_400(self):
        payload = {"percentile": 80.0, "category_label": "NOTACAT"}
        resp = _client.post("/api/predictions", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_student_linked_prediction(self):
        resp = _client.post(
            "/api/students",
            json={**_STUDENT_BASE, "name": "API Test — predict", "percentile": 88.0},
        )
        self.assertEqual(resp.status_code, 201)
        sid = resp.json()["id"]
        self._created.append(sid)

        resp2 = _client.post(f"/api/students/{sid}/predictions", json={"round_num": 1})
        self.assertEqual(resp2.status_code, 200)
        d = resp2.json()
        self.assertIn("safe", d)
        self.assertIn("probable", d)
        self.assertIn("reach", d)

    def test_student_linked_prediction_no_body(self):
        """Empty/no body should default to round_num=1."""
        resp = _client.post(
            "/api/students",
            json={**_STUDENT_BASE, "name": "API Test — predict nobdy"},
        )
        sid = resp.json()["id"]
        self._created.append(sid)

        resp2 = _client.post(f"/api/students/{sid}/predictions")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("safe", resp2.json())


class TestColleges(unittest.TestCase):
    def test_search_by_name_finds_coep(self):
        resp = _client.get("/api/colleges/search?q=COEP")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        self.assertGreater(len(results), 0)
        names = [r["college_name"] for r in results]
        self.assertTrue(
            any("COEP" in n for n in names),
            f"COEP not found in results: {names}",
        )

    def test_search_empty_q_returns_results(self):
        resp = _client.get("/api/colleges/search")
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()), 20)
        self.assertGreater(len(resp.json()), 0)

    def test_search_sort_by_percentile_orders_descending(self):
        resp = _client.get("/api/colleges/search?sort_by=percentile&limit=10")
        self.assertEqual(resp.status_code, 200)
        pcts = [r["top_percentile"] for r in resp.json() if r["top_percentile"] is not None]
        self.assertGreater(len(pcts), 0)
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_search_percentile_range_filter(self):
        resp = _client.get("/api/colleges/search?percentile_min=99&percentile_max=100&limit=50")
        self.assertEqual(resp.status_code, 200)
        for r in resp.json():
            if r["top_percentile"] is not None:
                self.assertGreaterEqual(r["top_percentile"], 99)
                self.assertLessEqual(r["top_percentile"], 100)

    def test_search_rejects_invalid_sort_by(self):
        resp = _client.get("/api/colleges/search?sort_by=bogus")
        self.assertEqual(resp.status_code, 422)

    def test_search_does_not_duplicate_name_mismatched_paired_codes(self):
        """K J Somaiya (3209/03209) carries two DIFFERENT college_name strings for
        the same physical college — regression guard for the bug where /search
        partitioned by exact name and showed both fragments as separate rows."""
        resp = _client.get("/api/colleges/search?q=K J Somaiya Institute&limit=50")
        self.assertEqual(resp.status_code, 200)
        codes = [r["college_code"] for r in resp.json()]
        self.assertIn(len([c for c in codes if c in ("3209", "03209")]), (0, 1))

    def test_college_profile_returns_full_shape(self):
        resp = _client.get("/api/colleges/6006")   # COEP 5-digit code
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertIn("identity", d)
        self.assertIn("accreditation", d)
        self.assertIn("facilities", d)
        self.assertIn("cutoff_trends", d)
        self.assertEqual(d["image_warning"], "CDN URLs — display only, do not proxy")

    def test_college_profile_not_found(self):
        resp = _client.get("/api/colleges/00000")
        self.assertEqual(resp.status_code, 404)

    def test_college_branches_returns_list(self):
        resp = _client.get("/api/colleges/6006/branches")
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertIn("branches", d)
        self.assertIsInstance(d["branches"], list)

    def test_college_branches_not_found(self):
        resp = _client.get("/api/colleges/00000/branches")
        self.assertEqual(resp.status_code, 404)

    def test_college_branches_include_2025_close_and_intake_fields(self):
        """Regression guard: the branches table must carry the real 2025 actual
        close (not just the 2026 prediction) and seat intake (general/TFWS),
        parsed from the official seat-matrix PDFs — never fabricated."""
        resp = _client.get("/api/colleges/6006/branches")
        self.assertEqual(resp.status_code, 200)
        branches = resp.json()["branches"]
        self.assertGreater(len(branches), 0)
        row = branches[0]
        self.assertIn("close_2025", row)
        self.assertIn("general_intake", row)
        self.assertIn("tfws_intake", row)
        # If intake is present, it must be a plausible positive seat count, never negative/zero-guessed.
        if row["general_intake"] is not None:
            self.assertGreater(row["general_intake"], 0)


class TestHealth(unittest.TestCase):
    def test_health_ok(self):
        resp = _client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertEqual(d["status"], "ok")
        self.assertTrue(d["engine_importable"])
        self.assertGreater(d["college_count"], 0)
        self.assertGreater(d["prediction_count"], 0)
        self.assertIn("edupath.db", d["db_path"])


class TestLookups(unittest.TestCase):
    def test_districts_non_empty(self):
        resp = _client.get("/api/lookups/districts")
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertIsInstance(d, list)
        self.assertGreater(len(d), 0)
        # Sentinel should NOT be in the API list (clients pass null directly)
        self.assertNotIn("Other / Not listed", d)

    def test_categories_have_label_and_code(self):
        resp = _client.get("/api/lookups/categories")
        self.assertEqual(resp.status_code, 200)
        cats = resp.json()
        self.assertGreater(len(cats), 0)
        self.assertIn("label", cats[0])
        self.assertIn("code", cats[0])

    def test_branch_keywords_non_empty(self):
        resp = _client.get("/api/lookups/branches")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.json()), 0)

    def test_cap_rounds(self):
        resp = _client.get("/api/lookups/cap-rounds")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [1, 2, 3])

    def test_stats_reflect_real_data_not_hardcoded_placeholders(self):
        """Regression guard for the homepage hero numbers that used to be
        literal fake strings ("11 yrs cutoff data", "36 districts")."""
        resp = _client.get("/api/lookups/stats")
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertGreater(d["college_count"], 0)
        self.assertGreater(d["district_count"], 0)
        self.assertEqual(d["cutoff_year_max"] - d["cutoff_year_min"] + 1 >= d["cutoff_year_count"], True)
        self.assertEqual(d["cutoff_year_count"], 3)  # 2023, 2024, 2025 — matches constants.YEAR_WEIGHTS


if __name__ == "__main__":
    unittest.main()
