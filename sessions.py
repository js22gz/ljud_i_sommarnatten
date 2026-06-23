"""Recording session configuration and path resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = ROOT / "sessions"
DOCS_DIR = ROOT / "docs"

AUDIO_EXTENSIONS = {".ogg", ".wav", ".mp3", ".flac", ".m4a"}
DEFAULTS = {
    "title": "Ljud i sommarnatten",
    "subtitle": "Trädgårdsfåglar — BirdNET-analys",
    "lat": 56.72564545228643,
    "lon": 16.112683711399647,
    "week": 25,
    "min_conf": 0.25,
    "sensitivity": 1.2,
    "overlap": 2.0,
    "merge_consecutive": 3,
    "merge_max_gap": 1.0,
    "analysis_skip_seconds": 0,
    "playback_lead_in_seconds": 10,
    "locale": "sv",
}


@dataclass(frozen=True)
class Session:
    id: str
    root: Path
    audio: Path
    analysis_audio: Path
    title: str
    subtitle: str
    lat: float
    lon: float
    week: int
    min_conf: float
    sensitivity: float
    overlap: float
    merge_consecutive: int
    merge_max_gap: float
    analysis_skip_seconds: float
    playback_lead_in_seconds: float
    locale: str
    bg_landscape: Path | None
    bg_portrait: Path | None

    @property
    def results_path(self) -> Path:
        return self.root / "results.json"

    @property
    def index_html(self) -> Path:
        return self.root / "index.html"


def list_sessions() -> list[str]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in SESSIONS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )


def _find_audio(session_dir: Path, preferred: str | None) -> Path:
    if preferred:
        audio = session_dir / preferred
        if audio.exists():
            return audio
        raise FileNotFoundError(f"Audio file not found for session: {audio}")

    matches = sorted(
        path
        for path in session_dir.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not matches:
        raise FileNotFoundError(
            f"No audio file in {session_dir}. Add one or set \"audio\" in session.json."
        )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise ValueError(
            f"Multiple audio files in {session_dir}: {names}. "
            "Set \"audio\" in session.json to pick one."
        )
    return matches[0]


def _optional_asset(session_dir: Path, name: str) -> Path | None:
    path = session_dir / name
    return path if path.exists() else None


def load_session(session_id: str) -> Session:
    session_dir = SESSIONS_DIR / session_id
    if not session_dir.is_dir():
        known = ", ".join(list_sessions()) or "(none)"
        raise SystemExit(f"Unknown session '{session_id}'. Available: {known}")

    config_path = session_dir / "session.json"
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    merged = {**DEFAULTS, **config}
    audio = _find_audio(session_dir, merged.get("audio"))
    analysis_preferred = merged.get("analysis_audio")
    if analysis_preferred:
        analysis_audio = session_dir / analysis_preferred
        if not analysis_audio.exists():
            raise FileNotFoundError(f"Analysis audio not found for session: {analysis_audio}")
    else:
        analysis_audio = audio

    return Session(
        id=session_id,
        root=session_dir,
        audio=audio,
        analysis_audio=analysis_audio,
        title=merged["title"],
        subtitle=merged["subtitle"],
        lat=float(merged["lat"]),
        lon=float(merged["lon"]),
        week=int(merged["week"]),
        min_conf=float(merged["min_conf"]),
        sensitivity=float(merged["sensitivity"]),
        overlap=float(merged["overlap"]),
        merge_consecutive=int(merged["merge_consecutive"]),
        merge_max_gap=float(merged["merge_max_gap"]),
        analysis_skip_seconds=float(merged["analysis_skip_seconds"]),
        playback_lead_in_seconds=float(merged["playback_lead_in_seconds"]),
        locale=str(merged["locale"]),
        bg_landscape=_optional_asset(session_dir, "landscape.jpg"),
        bg_portrait=_optional_asset(session_dir, "portrait.jpg"),
    )

