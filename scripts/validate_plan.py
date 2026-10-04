#!/usr/bin/env python3
"""Validation minimale du plan avant publication (duplicats, champs requis)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = ("date", "name", "external_id", "category")


def main() -> None:
    plan_path = ROOT / "workouts" / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert isinstance(plan, list) and plan, "Le plan ne doit pas etre vide."

    seen_ids: set[str] = set()
    for workout in plan:
        for field in REQUIRED_FIELDS:
            assert field in workout, f"Champ manquant '{field}' dans une seance : {workout}"
        assert workout["category"] in ("WORKOUT", "NOTE"), (
            f"category invalide pour {workout['external_id']}"
        )
        assert workout["external_id"] not in seen_ids, (
            f"external_id duplique dans le plan : {workout['external_id']}"
        )
        seen_ids.add(workout["external_id"])

    print(f"OK - {len(plan)} seance(s) validee(s).")


if __name__ == "__main__":
    main()
