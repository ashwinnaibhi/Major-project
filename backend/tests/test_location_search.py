"""Safe local tests for taluk filtering and request-origin distance handling.

The module redirects the application to a temporary SQLite database before importing
server.py. Tests never use the bundled project database, SMTP, broker services, or
external network APIs. Requests created by tests are NORMAL (not EMERGENCY).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DB = os.path.join(tempfile.gettempdir(), f"blood_donor_location_tests_{os.getpid()}.sqlite3")
for suffix in ("", "-wal", "-shm"):
    try:
        os.remove(TEST_DB + suffix)
    except FileNotFoundError:
        pass
os.environ["BLOODBANK_DB_FILE"] = TEST_DB
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class LocationSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(server.app)
        cls.client = cls.client_context.__enter__()
        conn = server.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM donors WHERE donor_id LIKE 'TEST-LOC-%'")
        cursor.execute("DELETE FROM blood_requests WHERE hospital_name = 'Location Search Test Hospital'")
        for donor_id, donor_name, email, latitude, longitude, score, is_available in (
            ("TEST-LOC-NEAR", "Near Test Donor", "near.location.test@example.invalid", 12.9716, 77.5946, 75.0, 1),
            ("TEST-LOC-FAR", "Far Test Donor", "far.location.test@example.invalid", 13.9716, 77.5946, 99.0, 1),
            ("TEST-LOC-NOCOORD", "Unlocated Test Donor", "no.coords.test@example.invalid", None, None, 90.0, 1),
            ("TEST-LOC-UNAVAILABLE", "Unavailable Test Donor", "unavailable.test@example.invalid", 12.9717, 77.5947, 100.0, 0),
        ):
            cursor.execute(
                """INSERT INTO donors
                   (donor_id, name, email, blood_group, age, gender, location,
                    district, taluk, latitude, longitude, is_available, availability_score)
                   VALUES (?, ?, ?, 'O+', 29, 'Other', 'Test locality',
                           'Bengaluru Urban', 'Anekal', ?, ?, ?, ?)""",
                (donor_id, donor_name, email, latitude, longitude, is_available, score),
            )
        cursor.execute(
            """INSERT INTO donors
               (donor_id, name, email, blood_group, age, gender, location, is_available, availability_score)
               VALUES ('TEST-LOC-LEGACY', 'Legacy Test Donor', 'legacy.location.test@example.invalid',
                       'O+', 30, 'Other', 'Zone A (Central)', 1, 80.0)"""
        )
        conn.commit()
        conn.close()

        response = cls.client.post(
            "/api/v1/requests",
            json={
                "hospital_name": "Location Search Test Hospital",
                "hospital_address": "Test address, no real facility",
                "contact_phone": "",
                "blood_group": "O+",
                "units_needed": 1,
                "urgency_level": "NORMAL",
                "patient_name": "Automated test case",
                "district": "Bengaluru Urban",
                "taluk": "Anekal",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
        )
        if response.status_code != 200:
            raise AssertionError(f"Test setup request failed: {response.status_code} {response.text}")
        cls.request_id = response.json()["id"]

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(TEST_DB + suffix)
            except FileNotFoundError:
                pass

    def test_location_catalog_is_data_driven_and_marked_non_authoritative(self):
        response = self.client.get("/api/v1/locations")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["authoritative"])
        self.assertIn("Bengaluru Urban", payload["districts"])
        self.assertIn("Anekal", payload["taluks_by_district"]["Bengaluru Urban"])
        self.assertNotIn("Zone A (Central)", payload["districts"])
        self.assertIn("authoritative", payload)
        self.assertFalse(payload["authoritative"])

    def test_empty_database_does_not_receive_synthetic_zone_donor_seeds(self):
        conn = server.get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM donors WHERE donor_id IN ('DNR-1001','DNR-1002','DNR-1003','DNR-1004')").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_legacy_zone_is_not_a_location_option_or_public_location_claim(self):
        response = self.client.get("/api/v1/donors", params={"blood_group": "O+"})
        self.assertEqual(response.status_code, 200, response.text)
        legacy = next(item for item in response.json() if item["donor_id"] == "TEST-LOC-LEGACY")
        self.assertEqual(legacy["location"], "Legacy location — not mapped")
        self.assertIsNone(legacy["district"])
        self.assertIsNone(legacy["taluk"])

    def test_combined_filters_and_radius_use_actual_request_coordinates(self):
        response = self.client.get(
            "/api/v1/donors",
            params={
                "blood_group": "O+",
                "district": "Bengaluru Urban",
                "taluk": "Anekal",
                "available_only": "true",
                "request_id": self.request_id,
                "radius_km": 10,
                "sort_by": "distance",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        donors = response.json()
        donor_ids = [donor["donor_id"] for donor in donors]
        self.assertIn("TEST-LOC-NEAR", donor_ids)
        self.assertNotIn("TEST-LOC-FAR", donor_ids)
        self.assertNotIn("TEST-LOC-NOCOORD", donor_ids)
        self.assertNotIn("TEST-LOC-UNAVAILABLE", donor_ids)
        self.assertEqual(donors[0]["distance_from_request_km"], 0.0)
        self.assertNotIn("latitude", donors[0])
        self.assertNotIn("longitude", donors[0])
        self.assertTrue(all(donor["district"] == "Bengaluru Urban" for donor in donors))
        self.assertTrue(all(donor["taluk"] == "Anekal" for donor in donors))

    def test_unavailable_distances_are_null_and_sorted_after_known_distances(self):
        response = self.client.get(
            "/api/v1/donors",
            params={
                "blood_group": "O+",
                "district": "Bengaluru Urban",
                "taluk": "Anekal",
                "available_only": "true",
                "request_id": self.request_id,
                "sort_by": "distance",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        donors = response.json()
        near = next(donor for donor in donors if donor["donor_id"] == "TEST-LOC-NEAR")
        unlocated = next(donor for donor in donors if donor["donor_id"] == "TEST-LOC-NOCOORD")
        self.assertEqual(near["distance_from_request_km"], 0.0)
        self.assertIsNone(unlocated["distance_from_request_km"])
        self.assertLess(donors.index(near), donors.index(unlocated))

    def test_request_without_coordinates_produces_unavailable_distance(self):
        response = self.client.post(
            "/api/v1/requests",
            json={
                "hospital_name": "Location Search Test Hospital",
                "hospital_address": "Legacy request without coordinates",
                "blood_group": "O+",
                "units_needed": 1,
                "urgency_level": "NORMAL",
                "patient_name": "Automated test case",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        request_id = response.json()["id"]
        donor_response = self.client.get("/api/v1/donors", params={"blood_group": "O+", "request_id": request_id})
        self.assertEqual(donor_response.status_code, 200, donor_response.text)
        self.assertTrue(all(item["distance_from_request_km"] is None for item in donor_response.json()))

    def test_invalid_coordinate_and_mismatched_taluk_are_rejected(self):
        base_payload = {
            "hospital_name": "Location Search Test Hospital",
            "hospital_address": "Test address",
            "blood_group": "O+",
            "units_needed": 1,
            "urgency_level": "NORMAL",
            "patient_name": "Automated test case",
        }
        bad_coordinates = self.client.post(
            "/api/v1/requests",
            json={**base_payload, "latitude": 91, "longitude": 77},
        )
        self.assertEqual(bad_coordinates.status_code, 400)

        bad_pair = self.client.post(
            "/api/v1/requests",
            json={**base_payload, "district": "Bengaluru Urban", "taluk": "Badami"},
        )
        self.assertEqual(bad_pair.status_code, 400)

    def test_haversine_calculates_great_circle_distance(self):
        distance = server.haversine_km(0, 0, 0, 1)
        self.assertAlmostEqual(distance, 111.195, delta=0.1)
        self.assertEqual(server.haversine_km(12.0, 77.0, 12.0, 77.0), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
