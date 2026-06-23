#!/usr/bin/env python3
"""Audit BirdNET species for likely false positives in a session."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from sessions import load_session

ROOT = Path(__file__).resolve().parent

def load_csv_rows(session) -> list[dict]:
    csv_path = session.root / f"{session.analysis_audio.stem}.BirdNET.results.csv"
    if not csv_path.exists():
        matches = sorted(session.root.glob("*.BirdNET.results.csv"))
        if len(matches) != 1:
            raise SystemExit(f"BirdNET CSV not found for {session.id}")
        csv_path = matches[0]
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def group_windows(rows: list[dict]) -> dict[tuple[float, float], list[dict]]:
    grouped: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in rows:
        key = (round(float(row["Start (s)"]), 1), round(float(row["End (s)"]), 1))
        grouped[key].append(row)
    return grouped


def rival_stats(scientific_name: str, windows: dict[tuple[float, float], list[dict]]) -> tuple[float, str | None, int]:
    confidences: list[float] = []
    losses: dict[str, int] = defaultdict(int)
    for rows in windows.values():
        mine = [row for row in rows if row["Scientific name"] == scientific_name]
        if not mine:
            continue
        my_conf = max(float(row["Confidence"]) for row in mine)
        confidences.append(my_conf)
        others = [row for row in rows if row["Scientific name"] != scientific_name]
        if not others:
            continue
        rival = max(others, key=lambda row: float(row["Confidence"]))
        if my_conf < float(rival["Confidence"]):
            losses[rival["Common name"]] += 1
    median = sorted(confidences)[len(confidences) // 2] if confidences else 0.0
    if not losses:
        return median, None, 0
    rival_name, rival_count = max(losses.items(), key=lambda item: item[1])
    return median, rival_name, rival_count


def classify(species: dict, median_raw: float) -> str:
    max_conf = species["max_confidence"]
    count = species["count"]
    # Heuristic flags only — exclusions.txt is the manual source of truth.
    if max_conf < 0.40 and count <= 2:
        return "review"
    if max_conf < 0.50 and count >= 10 and median_raw < 0.32:
        return "review"
    if max_conf < 0.65 and median_raw < 0.33 and count >= 15:
        return "review"
    return "keep"


def audit_session(session_id: str) -> None:
    session = load_session(session_id)
    results = json.loads(session.results_path.read_text(encoding="utf-8"))
    windows = group_windows(load_csv_rows(session))

    buckets: dict[str, list[tuple[str, str, float, int, float, str | None]]] = {
        "review": [],
        "keep": [],
    }
    for species in results["summary"]:
        median_raw, rival, rival_losses = rival_stats(species["scientific_name"], windows)
        bucket = classify(species, median_raw)
        buckets[bucket].append(
            (
                species["common_name"],
                species["scientific_name"],
                species["max_confidence"],
                species["count"],
                median_raw,
                f"{rival} ({rival_losses})" if rival else None,
            )
        )

    print(f"Session: {session_id}")
    print(f"Species in results: {len(results['summary'])}\n")

    for label, title in (
        ("review", "REVIEW (listen before excluding)"),
        ("keep", "LOOKS FINE"),
    ):
        rows = sorted(buckets[label], key=lambda item: (-item[3], -item[2]))
        print(f"=== {title} ({len(rows)}) ===")
        for common, scientific, max_conf, count, median_raw, rival in rows:
            rival_text = f"  rival: {rival}" if rival else ""
            print(
                f"  {common:<28} {scientific:<24} "
                f"x{count:3}  max {max_conf:>4.0%}  med {median_raw:>4.0%}{rival_text}"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit BirdNET species for likely false positives.")
    parser.add_argument("session", help="Session id under sessions/")
    args = parser.parse_args()
    audit_session(args.session)


if __name__ == "__main__":
    main()