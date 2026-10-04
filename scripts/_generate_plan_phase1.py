#!/usr/bin/env python3
"""Génère workouts/plan.json pour la phase 1 (05/10/2026 -> Hivernatrail 13/12/2026).

Script de génération ponctuel, pas une dépendance du pipeline de publication
(push_intervals.py lit directement workouts/plan.json, pas ce script). Gardé
dans le repo pour pouvoir régénérer/ajuster facilement si Lorin demande des
changements de structure plutôt que des changements séance par séance.

Hypothèses encodées ici (voir claude/profil-athlete.md et claude/objectifs-courses.md) :
- Allure seuil mesurée Garmin : 5:05/km -> travail d'allure autour de 4:50-5:20/km selon la semaine.
- Pas de cible d'allure rigide sur le terrain trail (cote, vallonne) : duree/effort uniquement.
- Hivernatrail 13/12/2026, 20km/550m D+, objectif 2h00.
- Semaine de decharge S5 (02-08/11), taper S9-S10 avant course.
"""

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "workouts" / "plan.json"

MON1 = date(2026, 10, 5)  # Lundi de la semaine 1


def d(week_idx: int, weekday: int) -> str:
    """week_idx: 0-based (semaine 1 = 0). weekday: 0=lundi ... 6=dimanche."""
    return (MON1 + timedelta(weeks=week_idx, days=weekday)).isoformat()


def step(duration_s, label=None, pace=None):
    s = {"type": "step", "duration": duration_s}
    if label:
        s["label"] = label
    if pace:
        s["target"] = {"type": "pace", "start": pace[0], "end": pace[1]}
    return s


def repeat(count, steps):
    return {"type": "repeat", "count": count, "steps": steps}


def mmss_to_s(m, s=0):
    return m * 60 + s


def workout(wk, wd, name, steps, intro=None, notes=None, slug=None):
    the_date = d(wk, wd)
    ext_slug = slug or name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
    return {
        "date": the_date,
        "name": name,
        "category": "WORKOUT",
        "sport": "Run",
        "external_id": f"trail-training:{the_date}-{ext_slug}",
        "steps": steps,
        **({"intro": intro} if intro else {}),
        **({"notes": notes} if notes else {}),
    }


def ef(wk, wd, minutes, label="Lundi — EF plat"):
    return workout(wk, wd, label, [step(minutes * 60, "EF facile, conversation possible")], slug="ef-lundi")


def echauff(minutes=20):
    return step(minutes * 60, "Echauffement facile")


def educatifs(minutes=10):
    return step(minutes * 60, "Educatifs (montees genoux, talons-fesses, skipping, foulees bondissantes)")


def rac(minutes=10):
    return step(minutes * 60, "Retour au calme facile")


PLAN = []

# ---- Mardi : allures (plat, cible d'allure) / cotes (route, pas de cible) ----
TUE_ALLURES = {
    0: (3, 8, (305, 315)),   # W1: 3x8min 5:05-5:15/km
    2: (4, 8, (300, 310)),   # W3: 4x8min 5:00-5:10/km
    4: (3, 5, (315, 325)),   # W5 (decharge): 3x5min 5:15-5:25/km
    6: (4, 10, (295, 305)),  # W7: 4x10min 4:55-5:05/km, r90s
    8: (3, 6, (290, 300)),   # W9: 3x6min 4:50-5:00/km (affutage)
}
TUE_ALLURES_RECUP = {0: 120, 2: 120, 4: 120, 6: 90, 8: 120}

TUE_COTES = {
    1: (8, 90),   # W2: 8x1'30
    3: (10, 90),  # W4: 10x1'30
    5: (8, 120),  # W6: 8x2'
    7: (10, 150), # W8: 10x2'30
}

for wk in range(9):  # semaines 1 a 9 (index 0-8), semaine 10 geree a part (taper)
    # Lundi EF
    mon_minutes = {0: 40, 1: 40, 2: 45, 3: 45, 4: 30, 5: 45, 6: 50, 7: 50, 8: 40}[wk]
    PLAN.append(ef(wk, 0, mon_minutes))

    # Mardi
    if wk in TUE_ALLURES:
        n, m, pace = TUE_ALLURES[wk]
        recup = TUE_ALLURES_RECUP[wk]
        PLAN.append(workout(
            wk, 1, f"Mardi — Seance allures ({n}x{m}min)",
            [echauff(20), educatifs(10), repeat(n, [step(m * 60, None, pace), step(recup, "recuperation")]), rac(10)],
            slug="mardi-allures",
        ))
    else:
        n, dur = TUE_COTES[wk]
        PLAN.append(workout(
            wk, 1, f"Mardi — Cotes ({n}x{dur}s)",
            [echauff(20), educatifs(10), repeat(n, [step(dur, "montee soutenue"), step(120, "recup trot/marche descente")]), rac(10)],
            slug="mardi-cotes",
        ))

    # Vendredi trail specifique (effort soutenu, pas de cible d'allure)
    fri_params = {
        0: (5, 240, 120), 1: (6, 240, 120), 2: (5, 300, 120), 3: (6, 300, 90),
        4: (4, 240, 120), 5: (6, 360, 90), 6: (5, 420, 90), 7: (4, 480, 120), 8: (3, 360, 120),
    }[wk]
    n, eff, rec = fri_params
    PLAN.append(workout(
        wk, 4, f"Vendredi — Trail specifique ({n}x{eff//60}min effort soutenu)",
        [echauff(15), repeat(n, [step(eff, "effort soutenu, au ressenti"), step(rec, "recuperation")]), rac(10)],
        slug="vendredi-trail-specifique",
    ))

    # Samedi trail continu effort soutenu
    sat_minutes = {0: 30, 1: 35, 2: 35, 3: 40, 4: 20, 5: 45, 6: 45, 7: 50, 8: 25}[wk]
    sat_label = "effort soutenu continu" if wk != 4 else "facile (semaine de decharge)"
    PLAN.append(workout(
        wk, 5, f"Samedi — Trail {sat_minutes}min",
        [echauff(15), step(sat_minutes * 60, sat_label), rac(10)],
        slug="samedi-trail",
    ))

    # Dimanche sortie longue
    long_minutes = {0: 120, 1: 135, 2: 135, 3: 150, 4: 90, 5: 150, 6: 150, 7: 165, 8: 120}[wk]
    if wk == 6:  # S7 (22/11) : bloc seuil 20min
        warm = (long_minutes - 20) // 2
        PLAN.append(workout(
            wk, 6, "Dimanche — Sortie longue + 20min seuil",
            [step(warm * 60, "EF, D+ libre"), step(20 * 60, None, (305, 320)), step((long_minutes - warm - 20) * 60, "EF, D+ libre, retour")],
            notes="Preparation specifique Hivernatrail : bloc continu a allure seuil sur portion roulante au milieu de la sortie.",
            slug="dimanche-sl-seuil20",
        ))
    elif wk == 7:  # S8 (29/11) : bloc seuil 30min
        warm = (long_minutes - 30) // 2
        PLAN.append(workout(
            wk, 6, "Dimanche — Sortie longue + 30min seuil",
            [step(warm * 60, "EF, D+ libre"), step(30 * 60, None, (305, 320)), step((long_minutes - warm - 30) * 60, "EF, D+ libre, retour")],
            notes="Repetition generale Hivernatrail : bloc seuil plus long, J-2 semaines.",
            slug="dimanche-sl-seuil30",
        ))
    else:
        PLAN.append(workout(
            wk, 6, f"Dimanche — Sortie longue {long_minutes // 60}h{long_minutes % 60:02d}",
            [step(long_minutes * 60, "EF stricte, D+ libre")],
            slug="dimanche-sl",
        ))

# ---- Semaine 10 : affutage + course (07/12 -> 13/12) ----
WK10 = 9
PLAN.append(ef(WK10, 0, 30, label="Lundi — Affutage facile"))
PLAN.append(workout(
    WK10, 1, "Mardi — Decrassage + accelerations",
    [step(25 * 60, "EF tres facile"), repeat(4, [step(20, "acceleration non chronometree"), step(100, "recuperation marche")])],
    slug="mardi-decrassage",
))
PLAN.append(workout(
    WK10, 4, "Vendredi — Tres facile",
    [step(20 * 60, "EF tres facile")],
    slug="vendredi-tres-facile",
))
PLAN.append(workout(
    WK10, 5, "Samedi — Veille de course",
    [step(20 * 60, "EF tres facile"), repeat(3, [step(15, "acceleration non chronometree"), step(105, "recuperation marche")])],
    slug="samedi-veille-course",
))

# Course Hivernatrail (NOTE, pas de cible, pas de steps structures)
PLAN.append({
    "date": d(WK10, 6),
    "name": "COURSE — HIVERNATRAIL 20km / 550m D+",
    "category": "NOTE",
    "sport": "Run",
    "external_id": f"trail-training:{d(WK10, 6)}-hivernatrail",
    "description": "Hivernatrail, Saint-Come-et-Maruejols (Gard). 20km / 550m D+. Objectif chrono : 2h00. Gerer l'effort au ressenti selon le denivele plutot qu'une allure kilometrique fixe.",
    "moving_time": 7200,
})

OUT.write_text(json.dumps(PLAN, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{len(PLAN)} seances ecrites dans {OUT}")
