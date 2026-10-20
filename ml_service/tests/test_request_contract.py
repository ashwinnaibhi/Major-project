"""Safe contract tests for the ML request schema and missing-artifact behavior.

These tests import the FastAPI module without entering its startup lifecycle, so the
serialized joblib artifact is never deserialized during the test run.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as ml_app


class MLRequestContractTests(unittest.TestCase):
    def test_karnataka_taluk_district_label_fits_existing_location_feature(self):
        request = ml_app.DonorPredictRequest(
            donor_id="SIMULATOR_INPUT",
            age=28,
            gender="Male",
            blood_group="O+",
            location="Anekal, Bengaluru Urban",
            distance_km=4.5,
            last_donation_days=120,
            donation_frequency=3,
            previous_response_rate=0.85,
            preferred_time="Morning",
            response_time_hrs=1.5,
            health_eligibility_score=95,
        )
        self.assertEqual(request.location, "Anekal, Bengaluru Urban")
        self.assertEqual(request.blood_group, "O+")

    def test_missing_model_artifact_fails_without_automatic_training(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_model = Path(temp_dir) / "missing-model.joblib"
            with patch.object(ml_app, "MODEL_PATH", str(missing_model)):
                with self.assertRaisesRegex(RuntimeError, "Automatic training is disabled"):
                    ml_app.load_model()
        self.assertIsNone(ml_app.pipeline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
