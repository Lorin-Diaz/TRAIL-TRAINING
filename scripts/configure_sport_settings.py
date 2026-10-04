#!/usr/bin/env python3
"""Configure automatiquement l'allure seuil course a pied sur Intervals.icu.

Correctif du 04/10/2026 : d'apres le forum officiel Intervals.icu (fil
"Pace targets lost in Garmin export for API-created running workouts"), si
l'allure seuil ("Run threshold pace") n'est pas renseignee dans les
reglages de sport d'un athlete, Intervals.icu supprime silencieusement les
cibles d'allure par etape lors de l'export vers Garmin Connect -- la montre
affiche alors "Pas de cible" meme quand workout_doc.steps est correct.

Ce script tourne a chaque execution du workflow GitHub Actions, AVANT la
publication des seances, pour que ce reglage ne soit jamais manquant --
sans que Lorin ait a y toucher manuellement dans l'interface Intervals.icu.
Il est idempotent : si l'allure est deja a jour, il ne fait rien.
"""

from __future__ import annotations

import os

import requests

API_BASE = "https://intervals.icu/api/v1"

# Allure seuil (1h, plat / piste) communiquee par Lorin le 04/10/2026 :
# 5'30/km, tenable sur 10 km a plat (nettement plus lent en trail, non
# utilise ici -- ce reglage ne sert qu'a la synchronisation Garmin des
# seances route/plat qui portent une cible d'allure explicite).
DEFAULT_THRESHOLD_PACE_SECS_PER_KM = 330.0


def mps_from_secs_per_km(seconds_per_km: float) -> float:
    return 1000.0 / seconds_per_km


def find_run_group(sport_settings: list[dict]) -> dict | None:
    for group in sport_settings:
        types = [t.lower() for t in (group.get("types") or [])]
        if "run" in types or "running" in types:
            return group
    return None


def main() -> None:
    api_key = os.environ["INTERVALS_API_KEY"]
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    target_pace = float(
        os.environ.get(
            "RUN_THRESHOLD_PACE_SECS_PER_KM", DEFAULT_THRESHOLD_PACE_SECS_PER_KM
        )
    )

    session = requests.Session()
    session.auth = ("API_KEY", api_key)

    response = session.get(f"{API_BASE}/athlete/{athlete_id}/sport-settings")
    response.raise_for_status()
    settings = response.json()

    group = find_run_group(settings)
    if group is None:
        print(
            "Aucun groupe de reglages 'Run' trouve sur Intervals.icu pour cet "
            "athlete -- rien a configurer (verifier le compte manuellement)."
        )
        return

    target_mps = mps_from_secs_per_km(target_pace)
    current_mps = group.get("threshold_pace")

    if current_mps is not None and abs(current_mps - target_mps) < 0.01:
        print(f"Allure seuil deja a jour ({current_mps:.3f} m/s).")
        return

    update = session.put(
        f"{API_BASE}/athlete/{athlete_id}/sport-settings/{group['id']}",
        json={"threshold_pace": target_mps},
    )
    update.raise_for_status()
    print(
        f"Allure seuil mise a jour : {target_pace:.0f} s/km "
        f"({target_mps:.3f} m/s)."
    )


if __name__ == "__main__":
    main()
