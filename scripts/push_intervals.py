#!/usr/bin/env python3
"""Publie les seances planifiees (workouts/plan.json) vers Intervals.icu.

Lecon retenue de l'ancien projet (voir doc projet
"restart-2026-10-04-architecture.md") : il ne suffit pas d'ecrire une cible
d'allure dans le texte de description (mot-cle "Pace") pour qu'elle arrive
jusqu'a la montre Garmin. Deux conditions supplementaires sont necessaires :

1. Le champ `target` de l'evenement Intervals.icu doit valoir "PACE" des
   qu'une etape porte une cible d'allure (sinon Garmin affiche "Pas de
   cible" meme si workout_doc.steps est correct cote serveur).
2. L'allure seuil course a pied doit etre configuree dans les reglages de
   sport Intervals.icu (voir scripts/configure_sport_settings.py), sinon
   Intervals.icu supprime silencieusement les cibles par etape a l'export
   Garmin.

Authentification : Basic Auth avec pour "utilisateur" la chaine litterale
"API_KEY" et pour mot de passe la cle API Intervals.icu (jamais ecrite en
dur ici : elle vient de la variable d'environnement INTERVALS_API_KEY,
injectee par GitHub Actions depuis les secrets du repository).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

API_BASE = "https://intervals.icu/api/v1"
EXTERNAL_ID_PREFIX = "trail-training:"


def _mmss(total_seconds: float) -> str:
    total_seconds = int(round(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _duration_text(duration_seconds: float) -> str:
    minutes = duration_seconds / 60
    if minutes == int(minutes):
        return f"{int(minutes)}min"
    return f"{duration_seconds:g}s"


def walk_steps(steps):
    """Parcourt recursivement les etapes, y compris a l'interieur des repeat."""
    for step in steps:
        if step.get("type") == "repeat":
            yield from walk_steps(step.get("steps", []))
        else:
            yield step


def has_pace_target(workout: dict) -> bool:
    return any(
        (step.get("target") or {}).get("type") == "pace"
        for step in walk_steps(workout.get("steps", []))
    )


def _step_lines(step: dict) -> list[str]:
    if step.get("type") == "repeat":
        lines = [f"{step['count']}x"]
        for sub in step.get("steps", []):
            lines.extend(f"  {line}" for line in _step_lines(sub))
        return lines

    duration_text = _duration_text(step["duration"])
    label = step.get("label", "").strip()
    target = step.get("target")
    if target and target.get("type") == "pace":
        pace_text = f"{_mmss(target['start'])}-{_mmss(target['end'])}/km Pace"
        text = f"- {duration_text} " + (f"{label} " if label else "") + pace_text
    else:
        text = f"- {duration_text}" + (f" {label}" if label else "")
    return [text]


def workout_description(workout: dict) -> str:
    lines: list[str] = []
    intro = workout.get("intro")
    if intro:
        lines.append(intro)
        lines.append("")
    for step in workout.get("steps", []):
        lines.extend(_step_lines(step))
    notes = workout.get("notes")
    if notes:
        lines.append("")
        lines.append(notes)
    return "\n".join(lines)


def run_event_payload(workout: dict) -> dict:
    category = workout.get("category", "WORKOUT")
    payload = {
        "category": category,
        "type": workout.get("sport", "Run"),
        "start_date_local": f"{workout['date']}T06:00:00",
        "name": workout["name"],
        "external_id": workout["external_id"],
    }

    if workout.get("steps"):
        payload["description"] = workout_description(workout)
    elif workout.get("description"):
        payload["description"] = workout["description"]

    if workout.get("moving_time"):
        payload["moving_time"] = workout["moving_time"]

    if category == "WORKOUT" and has_pace_target(workout):
        payload["target"] = "PACE"

    return payload


def load_plan(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def reconcile_external_ids(planned: list[dict], actual: list[dict]) -> tuple[int, int]:
    """Verifie l'idempotence : pas de doublon planifie, pas de doublon deja
    present cote Intervals.icu pour un meme external_id geree par ce depot."""
    actual_by_id: dict[str, list[dict]] = {}
    for event in actual:
        ext = event.get("external_id")
        if ext and ext.startswith(EXTERNAL_ID_PREFIX):
            actual_by_id.setdefault(ext, []).append(event)

    seen: set[str] = set()
    updated = created = 0
    for event in planned:
        ext = event["external_id"]
        if ext in seen:
            raise RuntimeError(f"external_id duplique dans le plan : {ext}")
        seen.add(ext)

        matches = actual_by_id.get(ext, [])
        if len(matches) > 1:
            raise RuntimeError(
                f"plusieurs evenements geres trouves pour external_id={ext}"
            )
        if matches:
            updated += 1
        else:
            created += 1
    return updated, created


def _session() -> requests.Session:
    api_key = os.environ["INTERVALS_API_KEY"]
    session = requests.Session()
    session.auth = ("API_KEY", api_key)
    return session


def fetch_existing_events(session: requests.Session, athlete_id: str, oldest: str, newest: str) -> list[dict]:
    response = session.get(
        f"{API_BASE}/athlete/{athlete_id}/events",
        params={"oldest": oldest, "newest": newest},
    )
    response.raise_for_status()
    return response.json()


def post_bulk(session: requests.Session, athlete_id: str, events: list[dict]) -> object:
    response = session.post(
        f"{API_BASE}/athlete/{athlete_id}/events/bulk",
        params={"upsert": "true"},
        json=events,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    plan_path = Path(sys.argv[1] if len(sys.argv) > 1 else "workouts/plan.json")

    plan = load_plan(plan_path)
    if not plan:
        print("Plan vide, rien a publier.")
        return

    session = _session()

    dates = sorted(w["date"] for w in plan)
    existing = fetch_existing_events(session, athlete_id, dates[0], dates[-1])
    updated, created = reconcile_external_ids(plan, existing)
    print(f"Idempotence verifiee : {updated} seance(s) a mettre a jour, {created} a creer.")

    events = [run_event_payload(workout) for workout in plan]
    result = post_bulk(session, athlete_id, events)
    print(f"{len(events)} seance(s) publiee(s) sur Intervals.icu.")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
