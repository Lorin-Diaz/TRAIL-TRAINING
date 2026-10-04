import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publisher", ROOT / "scripts/push_intervals.py")
publisher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = publisher
SPEC.loader.exec_module(publisher)


class PushIntervalsTests(unittest.TestCase):
    def test_pace_workout_sets_garmin_target(self):
        # Correctif 04/10/2026 : une etape a cible d'allure doit forcer
        # target="PACE" au niveau de l'evenement, sinon la cible
        # n'atteint jamais la montre Garmin (meme avec le mot-cle "Pace"
        # dans le texte de description).
        workout = {
            "date": "2026-10-11",
            "name": "Test allure cible",
            "category": "WORKOUT",
            "sport": "Run",
            "external_id": "trail-training:test-allure-cible",
            "steps": [
                {"type": "step", "duration": 600, "label": "Echauffement facile"},
                {
                    "type": "repeat",
                    "count": 3,
                    "steps": [
                        {
                            "type": "step",
                            "duration": 300,
                            "target": {"type": "pace", "start": 325, "end": 345},
                        },
                        {"type": "step", "duration": 120, "label": "recuperation"},
                    ],
                },
                {"type": "step", "duration": 300, "label": "Retour au calme"},
            ],
        }
        payload = publisher.run_event_payload(workout)
        self.assertEqual("PACE", payload.get("target"))
        self.assertIn("5:25-5:45/km Pace", payload["description"])
        self.assertIn("3x", payload["description"])

    def test_workout_without_pace_has_no_target(self):
        workout = {
            "date": "2026-10-12",
            "name": "Sortie facile",
            "category": "WORKOUT",
            "sport": "Run",
            "external_id": "trail-training:sortie-facile",
            "steps": [{"type": "step", "duration": 1800, "label": "facile"}],
        }
        payload = publisher.run_event_payload(workout)
        self.assertNotIn("target", payload)

    def test_note_category_never_gets_a_target(self):
        workout = {
            "date": "2026-10-13",
            "name": "Repere course",
            "category": "NOTE",
            "sport": "Run",
            "external_id": "trail-training:repere",
            "steps": [
                {
                    "type": "step",
                    "duration": 60,
                    "target": {"type": "pace", "start": 300, "end": 320},
                }
            ],
        }
        payload = publisher.run_event_payload(workout)
        self.assertNotIn("target", payload)

    def test_duplicate_external_id_in_plan_is_detected(self):
        planned = [
            {"external_id": "trail-training:a"},
            {"external_id": "trail-training:a"},
        ]
        with self.assertRaisesRegex(RuntimeError, "duplique"):
            publisher.reconcile_external_ids(planned, [])

    def test_duplicate_managed_event_on_intervals_is_detected(self):
        planned = [{"external_id": "trail-training:a"}]
        actual = [
            {"external_id": "trail-training:a"},
            {"external_id": "trail-training:a"},
        ]
        with self.assertRaisesRegex(RuntimeError, "plusieurs evenements"):
            publisher.reconcile_external_ids(planned, actual)

    def test_reconcile_counts_created_and_updated(self):
        planned = [
            {"external_id": "trail-training:new"},
            {"external_id": "trail-training:existing"},
        ]
        actual = [{"external_id": "trail-training:existing"}]
        updated, created = publisher.reconcile_external_ids(planned, actual)
        self.assertEqual(1, updated)
        self.assertEqual(1, created)


if __name__ == "__main__":
    unittest.main()
