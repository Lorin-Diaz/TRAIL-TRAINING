#!/usr/bin/env python3
"""Liste (lecture seule, aucune suppression) les evenements residuels de
l'ancien plan abandonne ("cub27-v1") encore presents sur Intervals.icu.

Voir claude/restart-2026-10-04-architecture.md pour le contexte : l'ancien
pipeline (supprime de GitHub) avait pousse ces evenements avant le
redemarrage du 04/10/2026 ; supprimer le repository ne les a pas supprimes
cote Intervals.icu.

Ce script ne fait que lister (GET) -- aucune suppression. La suppression
reste une action volontaire, faite par Lorin lui-meme sur Intervals.icu.

Le marqueur "cub27-v1-..." peut se trouver soit dans le champ external_id,
soit en texte libre dans la description (observe le 04/10/2026 : l'ancien
script ecrivait "Source-ID : cub27-v1-..." dans la description plutot que
dans le champ external_id dedie de l'API) -- on verifie donc les deux.

Usage : python scripts/list_old_plan_residuals.py [oldest] [newest]
"""

from __future__ import annotations

import os
import sys

import requests

API_BASE = "https://intervals.icu/api/v1"
OLD_PLAN_PREFIX = "cub27-v1-"


def _session() -> requests.Session:
    api_key = os.environ["INTERVALS_API_KEY"]
    session = requests.Session()
    session.auth = ("API_KEY", api_key)
    return session


def fetch_events(session: requests.Session, athlete_id: str, oldest: str, newest: str) -> list[dict]:
    response = session.get(
        f"{API_BASE}/athlete/{athlete_id}/events",
        params={"oldest": oldest, "newest": newest},
    )
    response.raise_for_status()
    return response.json()


def is_old_plan(e: dict) -> bool:
    ext = e.get("external_id") or ""
    desc = e.get("description") or ""
    return ext.startswith(OLD_PLAN_PREFIX) or OLD_PLAN_PREFIX in desc


def main() -> None:
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    oldest = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01"
    newest = sys.argv[2] if len(sys.argv) > 2 else "2027-12-31"

    session = _session()
    events = fetch_events(session, athlete_id, oldest, newest)

    residuals = sorted(
        (e for e in events if is_old_plan(e)),
        key=lambda e: e.get("start_date_local", ""),
    )

    print(f"{len(events)} evenement(s) au total entre {oldest} et {newest}.")
    print(f"{len(residuals)} residu(s) de l'ancien plan ({OLD_PLAN_PREFIX}...) a supprimer :")
    print()
    for e in residuals:
        date = (e.get("start_date_local") or "?")[:10]
        print(f"- {date} | {e.get('name', '?')} | id={e['id']} | external_id={e.get('external_id')}")


if __name__ == "__main__":
    main()
