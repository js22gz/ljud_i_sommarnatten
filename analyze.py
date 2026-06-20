#!/usr/bin/env python3
"""Analyze backyard bird recordings with BirdNET (same tech as Merlin Sound ID)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import soundfile as sf

from sessions import load_session

ROOT = Path(__file__).resolve().parent
DEFAULT_EXCLUSIONS = ROOT / "exclusions.txt"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def load_exclusions(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def apply_exclusions(detections: list[dict], exclusions: set[str]) -> list[dict]:
    if not exclusions:
        return detections
    return [
        det
        for det in detections
        if det["scientific_name"] not in exclusions and det["common_name"] not in exclusions
    ]


def run_birdnet(
    audio: Path,
    output_dir: Path,
    *,
    lat: float,
    lon: float,
    week: int,
    min_conf: float,
    locale: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)

    cmd = [
        str(python),
        "-m",
        "birdnet_analyzer.analyze",
        str(audio),
        "-o",
        str(output_dir),
        "--rtype",
        "csv",
        "--min_conf",
        str(min_conf),
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--week",
        str(week),
        "-l",
        locale,
        "--overlap",
        "1.5",
        "--sensitivity",
        "1.1",
    ]

    print("Running BirdNET analysis...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

    csv_files = sorted(output_dir.glob("*.BirdNET.results.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No BirdNET CSV results found in {output_dir}")

    return csv_files[0]


def parse_csv(csv_path: Path) -> list[dict]:
    import csv

    detections: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            start = float(row["Start (s)"])
            end = float(row["End (s)"])
            scientific, common = row["Scientific name"], row["Common name"]
            confidence = float(row["Confidence"])
            detections.append(
                {
                    "start": start,
                    "end": end,
                    "duration": round(end - start, 2),
                    "scientific_name": scientific,
                    "common_name": common,
                    "confidence": round(confidence, 4),
                    "label": f"{common} ({scientific})",
                }
            )
    return detections


def build_summary(detections: list[dict]) -> list[dict]:
    by_species: dict[str, dict] = {}
    for det in detections:
        key = det["scientific_name"]
        if key not in by_species:
            by_species[key] = {
                "scientific_name": det["scientific_name"],
                "common_name": det["common_name"],
                "count": 0,
                "max_confidence": 0.0,
                "total_duration": 0.0,
            }
        entry = by_species[key]
        entry["count"] += 1
        entry["max_confidence"] = max(entry["max_confidence"], det["confidence"])
        entry["total_duration"] += det["duration"]

    summary = sorted(
        by_species.values(),
        key=lambda item: (item["count"], item["max_confidence"]),
        reverse=True,
    )
    for item in summary:
        item["max_confidence"] = round(item["max_confidence"], 4)
        item["total_duration"] = round(item["total_duration"], 2)
    return summary


def compute_waveform_peaks(audio: Path, *, buckets: int = 1200) -> list[float]:
    data, _samplerate = sf.read(audio, always_2d=True)
    mono = data.mean(axis=1)
    chunk = max(1, len(mono) // buckets)
    peaks: list[float] = []
    for index in range(0, len(mono), chunk):
        segment = mono[index : index + chunk]
        peaks.append(float(abs(segment).max()) if len(segment) else 0.0)
    max_peak = max(peaks) or 1.0
    return [round(value / max_peak, 4) for value in peaks]


def write_results_json(
    *,
    audio: Path,
    detections: list[dict],
    summary: list[dict],
    peaks: list[float],
    meta: dict,
    output_path: Path,
) -> None:
    payload = {
        "meta": meta,
        "audio_file": audio.name,
        "duration_seconds": meta["duration_seconds"],
        "detection_count": len(detections),
        "species_count": len(summary),
        "waveform_peaks": peaks,
        "summary": summary,
        "detections": detections,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Identify birds in a recording using BirdNET.")
    parser.add_argument("--session", help="Recording session id (folder under sessions/)")
    parser.add_argument("--audio", type=Path, help="Override audio file path")
    parser.add_argument("--output", type=Path, help="Override output directory")
    parser.add_argument("--lat", type=float, help="Recording latitude")
    parser.add_argument("--lon", type=float, help="Recording longitude")
    parser.add_argument("--week", type=int, help="Week of year 1-48 (midsummer ≈ 25)")
    parser.add_argument("--min-conf", type=float, dest="min_conf", help="Minimum BirdNET confidence")
    parser.add_argument("--locale", help="Species name locale (sv, en_us, ...)")
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=DEFAULT_EXCLUSIONS,
        help="File with scientific/common names to exclude as false positives",
    )
    parser.add_argument(
        "--skip-birdnet",
        action="store_true",
        help="Reuse existing BirdNET CSV in output folder",
    )
    args = parser.parse_args()

    if not args.session:
        raise SystemExit("Provide --session <id>. Use 'python run.py --list' to see sessions.")

    session = load_session(args.session)
    audio = args.audio or session.audio
    output_dir = args.output or session.root
    lat = args.lat if args.lat is not None else session.lat
    lon = args.lon if args.lon is not None else session.lon
    week = args.week if args.week is not None else session.week
    min_conf = args.min_conf if args.min_conf is not None else session.min_conf
    locale = args.locale or session.locale

    if not audio.exists():
        raise SystemExit(f"Audio file not found: {audio}")

    info = sf.info(audio)
    if args.skip_birdnet:
        csv_files = sorted(output_dir.glob("*.BirdNET.results.csv"))
        if not csv_files:
            raise SystemExit(f"No BirdNET CSV found in {output_dir}. Run without --skip-birdnet first.")
        csv_path = csv_files[0]
    else:
        csv_path = run_birdnet(
            audio,
            output_dir,
            lat=lat,
            lon=lon,
            week=week,
            min_conf=min_conf,
            locale=locale,
        )

    exclusions = load_exclusions(args.exclusions)
    detections = apply_exclusions(parse_csv(csv_path), exclusions)
    summary = build_summary(detections)
    peaks = compute_waveform_peaks(audio)

    meta = {
        "title": session.title,
        "subtitle": session.subtitle,
        "engine": "BirdNET 2.4 (Cornell Lab — same family as Merlin Sound ID)",
        "location": {"lat": lat, "lon": lon},
        "week": week,
        "locale": locale,
        "min_confidence": min_conf,
        "duration_seconds": round(info.duration, 2),
        "sample_rate": info.samplerate,
        "channels": info.channels,
    }

    results_path = output_dir / "results.json"
    write_results_json(
        audio=audio,
        detections=detections,
        summary=summary,
        peaks=peaks,
        meta=meta,
        output_path=results_path,
    )

    if exclusions:
        print(f"Excluded {len(exclusions)} name(s) from {args.exclusions.name}: {', '.join(sorted(exclusions))}")

    print(f"\nFound {len(summary)} species in {len(detections)} detections")
    for index, species in enumerate(summary[:12], start=1):
        print(
            f"  {index:2}. {species['common_name']:<28} "
            f"×{species['count']:3}  max {species['max_confidence']:.0%}"
        )
    if len(summary) > 12:
        print(f"  ... and {len(summary) - 12} more")
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()