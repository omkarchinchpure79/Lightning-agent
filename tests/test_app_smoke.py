"""
Cold-load smoke test for the Streamlit app.

Catches the class of demo-blocker that 42 unit tests missed: the app failing to
render its sidebar form on a fresh load (e.g. an adapter function gone missing,
a broken import chain, or a removed form submit button).

NOTE ON SCOPE: this loads the app FRESH (AppTest re-imports each run), so it
verifies the source is internally consistent. It does NOT reproduce a stale
long-running `streamlit run` server that cached an old sub-module across edits —
that operational failure mode is fixed by restarting the server, not by a test.
What this DOES catch: if `district_options` were ever renamed/removed, if the
district dropdown stopped populating, or if the form lost its submit button.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

APP = os.path.join(os.path.dirname(__file__), "..", "app", "streamlit_app.py")


class TestAppColdLoad(unittest.TestCase):
    def test_sidebar_form_renders_on_cold_load(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP, default_timeout=60).run()

        # 1. No exception on cold load (would have caught the AttributeError).
        self.assertEqual(list(at.exception), [],
                         f"App raised on cold load: {list(at.exception)}")

        # 2. The Home-district selectbox rendered AND was populated by
        #    engine_adapter.district_options() — the 'Other / Not listed' sentinel
        #    only exists if that call succeeded.
        labels = [sb.label for sb in at.selectbox]
        self.assertIn("Home district", labels,
                      "district selectbox missing — district_options() failed")
        district_sb = next(sb for sb in at.selectbox if sb.label == "Home district")
        self.assertIn("Other / Not listed", list(district_sb.options),
                      "district dropdown not populated by district_options()")

        # 3. The sidebar form has its submit button (would have caught the
        #    'Missing Submit Button' symptom directly).
        btn_labels = [b.label or "" for b in at.button]
        self.assertTrue(
            any("Generate preference list" in b for b in btn_labels),
            "Sidebar form has no submit button (form_submit_button missing)")


if __name__ == "__main__":
    unittest.main()
