#!/usr/bin/env python3
"""Build a self-contained HTML visualizer from BirdNET results."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sessions import DOCS_DIR, load_session

ROOT = Path(__file__).resolve().parent


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Ljud i sommarnatten — fågelanalys</title>
  <style>
    :root {
      --bg: #0b1220;
      --panel: #121a2b;
      --panel-2: #18233a;
      --text: #e8eefc;
      --muted: #9db0d3;
      --accent: #6ee7b7;
      --accent-2: #fbbf24;
      --line: rgba(255,255,255,0.08);
      --shadow: 0 18px 50px rgba(0,0,0,0.35);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(110,231,183,0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(251,191,36,0.10), transparent 24%),
        linear-gradient(180deg, #08101d 0%, var(--bg) 100%);
      min-height: 100vh;
    }

    .wrap {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 64px;
      text-align: center;
    }
    header { margin-bottom: 28px; }
    h1 {
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.2rem);
      letter-spacing: -0.03em;
      line-height: 1.05;
      max-width: 100%;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    @media (max-width: 960px) {
      h1 {
        font-size: clamp(0.78rem, 4.2vw, 3.2rem);
      }
    }

    .card {
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .player-section {
      background: transparent;
      border-color: transparent;
      box-shadow: none;
    }
    .card-body { padding: 18px 20px 22px; }

    .player {
      display: grid;
      gap: 14px;
    }
    .audio-hidden {
      position: absolute;
      width: 0;
      height: 0;
      opacity: 0;
      pointer-events: none;
    }
    .time {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 5;
      display: flex;
      justify-content: center;
      gap: 1rem;
      padding: 8px 44px;
      font-size: 0.82rem;
      color: var(--text);
      background: linear-gradient(to top, rgba(8, 16, 29, 0.72), transparent);
      pointer-events: none;
    }
    #currentTime {
      cursor: pointer;
      user-select: none;
      pointer-events: auto;
    }
    #currentTime:hover { color: var(--accent); }

    .wave-wrap {
      position: relative;
      height: 120px;
      border-radius: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      overflow: hidden;
      cursor: pointer;
      touch-action: manipulation;
      user-select: none;
    }
    #waveCanvas, #timelineCanvas {
      position: absolute; inset: 0; width: 100%; height: 100%;
    }
    #playhead {
      position: absolute; top: 0; bottom: 0; width: 2px;
      background: var(--accent-2);
      box-shadow: 0 0 12px rgba(251,191,36,0.8);
      pointer-events: none;
      transform: translateX(0);
      z-index: 3;
    }
    .play-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(8, 16, 29, 0.38);
      opacity: 1;
      transition: opacity 0.2s ease;
      z-index: 4;
      pointer-events: none;
    }
    .wave-wrap.is-playing .play-overlay {
      opacity: 0;
      pointer-events: none;
    }
    .play-overlay svg {
      width: 52px;
      height: 52px;
      fill: rgba(232, 238, 252, 0.92);
      filter: drop-shadow(0 4px 16px rgba(0, 0, 0, 0.35));
    }
    .volume-slider {
      position: absolute;
      right: 10px;
      top: 14px;
      bottom: 14px;
      width: 30px;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 12px;
      background: rgba(18, 26, 43, 0.55);
      backdrop-filter: blur(4px);
      border: 1px solid var(--line);
    }
    .volume-track {
      position: relative;
      width: 4px;
      height: calc(100% - 8px);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      cursor: pointer;
      touch-action: none;
    }
    .volume-fill {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      border-radius: 999px;
      background: linear-gradient(to top, rgba(110, 231, 183, 0.35), var(--accent));
      pointer-events: none;
    }
    .volume-thumb {
      position: absolute;
      left: 50%;
      width: 14px;
      height: 14px;
      margin: 0;
      padding: 0;
      border: 2px solid rgba(232, 238, 252, 0.92);
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 10px rgba(110, 231, 183, 0.45);
      transform: translate(-50%, 50%);
      cursor: grab;
      touch-action: none;
    }
    .volume-thumb:active { cursor: grabbing; }

    .legend {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(18, 26, 43, 0.55);
      backdrop-filter: blur(6px);
      border: 1px solid var(--line);
    }
    .legend-item {
      --highlight-strength: 0;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 1.05rem;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid transparent;
      border-radius: 999px;
      padding: 8px 14px;
      transition: color 0.3s ease, background 0.4s ease, border-color 0.4s ease,
        box-shadow 0.4s ease, transform 0.4s ease;
    }
    .legend-item.active {
      color: var(--text);
      background: rgba(110, 231, 183, calc(0.06 + var(--highlight-strength) * 0.4));
      border-color: rgba(110, 231, 183, calc(0.15 + var(--highlight-strength) * 0.8));
      box-shadow: 0 0 calc(4px + var(--highlight-strength) * 22px)
        rgba(110, 231, 183, calc(0.1 + var(--highlight-strength) * 0.6));
      transform: scale(calc(1 + var(--highlight-strength) * 0.07));
    }
    .swatch {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      transition: transform 0.4s ease;
    }
    .legend-item.active .swatch {
      transform: scale(calc(1 + var(--highlight-strength) * 0.25));
    }

    footer {
      margin-top: 28px;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
    }
    footer a {
      color: var(--accent);
      text-decoration: none;
    }
    footer a:hover { text-decoration: underline; }

    __BACKGROUND_CSS__
  </style>
</head>
<body class="__BODY_CLASS__">
  <div class="wrap">
    <header>
      <h1 id="title">Ljud i sommarnatten</h1>
    </header>

    <section class="card player-section">
      <div class="card-body player">
        <audio id="audio" class="audio-hidden" preload="metadata"></audio>
        <div class="wave-wrap" id="waveWrap" role="button" aria-label="Spela inspelning" tabindex="0">
          <canvas id="waveCanvas"></canvas>
          <canvas id="timelineCanvas"></canvas>
          <div id="playhead"></div>
          <div class="play-overlay" id="playOverlay" aria-hidden="true">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
          <div class="volume-slider" id="volumeSlider" aria-label="Volym">
            <div class="volume-track" id="volumeTrack">
              <div class="volume-fill" id="volumeFill"></div>
              <button type="button" class="volume-thumb" id="volumeThumb" aria-label="Volym"></button>
            </div>
          </div>
          <div class="time"><span id="currentTime">0:00</span><span id="totalTime">0:00</span></div>
        </div>
        <div class="legend" id="legend"></div>
      </div>
    </section>

    <footer>
      Fågelidentifiering med <a href="https://birdnet.cornell.edu" target="_blank" rel="noopener">BirdNET</a> (Cornell Lab of Ornithology).
    </footer>
  </div>

  <script>
    (async function () {
    const COLORS = [
      "#6ee7b7", "#fbbf24", "#60a5fa", "#f472b6", "#a78bfa",
      "#34d399", "#fb7185", "#38bdf8", "#f59e0b", "#c084fc",
      "#4ade80", "#fda4af", "#93c5fd", "#fcd34d", "#86efac"
    ];

    const data = await (await fetch("results.json")).json();
    const audio = document.getElementById("audio");
    const waveWrap = document.getElementById("waveWrap");
    const waveCanvas = document.getElementById("waveCanvas");
    const timelineCanvas = document.getElementById("timelineCanvas");
    const playhead = document.getElementById("playhead");
    const duration = data.duration_seconds;

    function getDuration() {
      return Number.isFinite(audio.duration) && audio.duration > 0
        ? audio.duration
        : duration;
    }

    function seekToRatio(ratio) {
      const target = Math.max(0, Math.min(1, ratio)) * getDuration();
      audio.currentTime = target;
      return target;
    }

    function playFromRatio(ratio) {
      const wasPaused = audio.paused;
      seekToRatio(ratio);
      if (!wasPaused) {
        return;
      }

      let started = false;
      const startPlayback = () => {
        if (started) {
          return;
        }
        started = true;
        audio.play().catch(() => {});
      };

      if (audio.seeking) {
        audio.addEventListener("seeked", startPlayback, { once: true });
        setTimeout(startPlayback, 800);
      } else {
        startPlayback();
      }
    }

    function setPlayingState(isPlaying) {
      waveWrap.classList.toggle("is-playing", isPlaying);
      waveWrap.setAttribute("aria-label", isPlaying ? "Pausa inspelning" : "Spela inspelning");
    }

    const colorBySpecies = new Map();
    const legendHolds = new Map();
    const LEGEND_MIN_CONFIDENCE = 0.4;

    data.summary.forEach((species, index) => {
      colorBySpecies.set(species.scientific_name, COLORS[index % COLORS.length]);
    });

    function formatTime(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
      return `${mins}:${secs}`;
    }

    function setupHeader() {
      const title = document.getElementById("title");
      title.textContent = data.audio_file;
      title.title = data.audio_file;
    }

    function setupLegend() {
      const legend = document.getElementById("legend");
      legend.innerHTML = data.summary.slice(0, 8).map(species => {
        const color = colorBySpecies.get(species.scientific_name);
        return `<span class="legend-item" data-species="${species.scientific_name}"><span class="swatch" style="background:${color}"></span>${species.common_name}</span>`;
      }).join("");
    }

    function holdAfterSeconds(confidence) {
      return 0.15 + confidence * confidence * 2.5;
    }

    function updateLegendHighlights(currentTime) {
      for (const det of data.detections) {
        if (
          currentTime >= det.start &&
          currentTime <= det.end &&
          det.confidence >= LEGEND_MIN_CONFIDENCE
        ) {
          const untilTime = det.end + holdAfterSeconds(det.confidence);
          const existing = legendHolds.get(det.scientific_name);
          legendHolds.set(det.scientific_name, {
            untilTime: Math.max(untilTime, existing?.untilTime ?? 0),
            strength: Math.max(det.confidence, existing?.strength ?? 0),
          });
        }
      }

      for (const [species, state] of [...legendHolds.entries()]) {
        if (currentTime > state.untilTime) {
          legendHolds.delete(species);
        }
      }

      document.querySelectorAll(".legend-item").forEach((item) => {
        const state = legendHolds.get(item.dataset.species);
        const isActive = Boolean(state);
        item.classList.toggle("active", isActive);
        item.style.setProperty("--highlight-strength", isActive ? String(state.strength) : "0");
      });
    }

    function resizeCanvas(canvas, wrap) {
      const rect = wrap.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      return { ctx, width: rect.width, height: rect.height };
    }

    function drawWaveform() {
      const wrap = document.getElementById("waveWrap");
      const { ctx, width, height } = resizeCanvas(waveCanvas, wrap);
      const peaks = data.waveform_peaks;
      const mid = height / 2;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "rgba(255,255,255,0.03)";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "rgba(157,176,211,0.85)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      peaks.forEach((peak, index) => {
        const x = (index / (peaks.length - 1)) * width;
        const amp = peak * (height * 0.38);
        ctx.moveTo(x, mid - amp);
        ctx.lineTo(x, mid + amp);
      });
      ctx.stroke();
    }

    function drawDetectionOverlay() {
      const wrap = document.getElementById("waveWrap");
      const { ctx, width, height } = resizeCanvas(timelineCanvas, wrap);
      ctx.clearRect(0, 0, width, height);
      data.detections.forEach(det => {
        const x = (det.start / duration) * width;
        const w = Math.max(2, ((det.end - det.start) / duration) * width);
        ctx.fillStyle = colorBySpecies.get(det.scientific_name) + "55";
        ctx.fillRect(x, 8, w, height - 16);
      });
    }

    function updatePlayhead() {
      const wrap = document.getElementById("waveWrap");
      const ratio = audio.currentTime / duration;
      playhead.style.left = `${ratio * wrap.clientWidth}px`;
      document.getElementById("currentTime").textContent = formatTime(audio.currentTime);
      updateLegendHighlights(audio.currentTime);
    }

    function setupVolumeSlider() {
      const volumeSlider = document.getElementById("volumeSlider");
      const volumeTrack = document.getElementById("volumeTrack");
      const volumeFill = document.getElementById("volumeFill");
      const volumeThumb = document.getElementById("volumeThumb");
      let isDragging = false;

      function setVolume(value) {
        const volume = Math.max(0, Math.min(1, value));
        audio.volume = volume;
        audio.muted = volume === 0;
        volumeFill.style.height = `${volume * 100}%`;
        volumeThumb.style.bottom = `${volume * 100}%`;
        volumeThumb.setAttribute("aria-valuenow", String(Math.round(volume * 100)));
      }

      function volumeFromClientY(clientY) {
        const rect = volumeTrack.getBoundingClientRect();
        const ratio = 1 - (clientY - rect.top) / rect.height;
        return Math.max(0, Math.min(1, ratio));
      }

      function stopDragging() {
        isDragging = false;
      }

      volumeSlider.addEventListener("pointerdown", (event) => event.stopPropagation());
      volumeSlider.addEventListener("click", (event) => event.stopPropagation());

      volumeTrack.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        isDragging = true;
        volumeTrack.setPointerCapture(event.pointerId);
        setVolume(volumeFromClientY(event.clientY));
      });

      volumeTrack.addEventListener("pointermove", (event) => {
        if (!isDragging) return;
        setVolume(volumeFromClientY(event.clientY));
      });

      volumeTrack.addEventListener("pointerup", stopDragging);
      volumeTrack.addEventListener("pointercancel", stopDragging);

      setVolume(audio.volume || 1);
    }

    function setupInteractions() {
      setupVolumeSlider();

      const LONG_PRESS_MS = 450;
      let longPressTimer = null;
      let longPressTriggered = false;
      let hasPlayed = false;

      function isWaveTarget(event) {
        return !event.target.closest(".volume-slider");
      }

      function ratioFromEvent(event) {
        const rect = waveWrap.getBoundingClientRect();
        return (event.clientX - rect.left) / rect.width;
      }

      function clearLongPressTimer() {
        if (longPressTimer) {
          clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      }

      waveWrap.addEventListener("pointerdown", (event) => {
        if (!isWaveTarget(event)) {
          return;
        }
        longPressTriggered = false;
        clearLongPressTimer();
        longPressTimer = setTimeout(() => {
          longPressTriggered = true;
          if (!audio.paused) {
            audio.pause();
          }
        }, LONG_PRESS_MS);
      });

      waveWrap.addEventListener("pointerup", clearLongPressTimer);
      waveWrap.addEventListener("pointercancel", () => {
        clearLongPressTimer();
        longPressTriggered = false;
      });

      waveWrap.addEventListener("click", (event) => {
        if (!isWaveTarget(event)) {
          return;
        }
        if (longPressTriggered) {
          longPressTriggered = false;
          return;
        }
        if (!hasPlayed) {
          playFromRatio(0);
          return;
        }
        playFromRatio(ratioFromEvent(event));
      });

      waveWrap.addEventListener("contextmenu", (event) => {
        if (isWaveTarget(event)) {
          event.preventDefault();
        }
      });

      waveWrap.addEventListener("keydown", (event) => {
        if (event.code === "Space" || event.code === "Enter") {
          event.preventDefault();
          if (audio.paused) {
            audio.play();
          } else {
            audio.pause();
          }
        }
      });

      document.getElementById("currentTime").addEventListener("click", () => {
        if (audio.paused) {
          audio.play();
        } else {
          audio.pause();
        }
      });

      audio.addEventListener("play", () => {
        hasPlayed = true;
        setPlayingState(true);
      });
      audio.addEventListener("pause", () => setPlayingState(false));
      audio.addEventListener("ended", () => setPlayingState(false));
      audio.addEventListener("timeupdate", updatePlayhead);
      audio.addEventListener("loadedmetadata", () => {
        document.getElementById("totalTime").textContent = formatTime(audio.duration || duration);
        drawWaveform();
        drawDetectionOverlay();
        updatePlayhead();
        setPlayingState(!audio.paused);
      });
      window.addEventListener("resize", () => {
        drawWaveform();
        drawDetectionOverlay();
        updatePlayhead();
      });
    }

    audio.src = "__AUDIO_FILE__";
    setupHeader();
    setupLegend();
    setupInteractions();
    })();
  </script>
</body>
</html>
"""


def build_background_css(landscape: Path | None, portrait: Path | None) -> tuple[str, str]:
    if not landscape or not portrait:
        return "", ""

    landscape_name = landscape.name
    portrait_name = portrait.name
    css = f"""
    body.has-photo-bg {{
      background: #08101d;
      isolation: isolate;
    }}
    body.has-photo-bg::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
      transform: translateZ(0);
      pointer-events: none;
    }}
    @media (orientation: landscape) {{
      body.has-photo-bg::before {{
        background-image:
          linear-gradient(180deg, rgba(8, 16, 29, 0.22) 0%, rgba(8, 16, 29, 0.48) 100%),
          url("{landscape_name}");
      }}
    }}
    @media (orientation: portrait) {{
      body.has-photo-bg::before {{
        background-image:
          linear-gradient(180deg, rgba(8, 16, 29, 0.22) 0%, rgba(8, 16, 29, 0.48) 100%),
          url("{portrait_name}");
      }}
    }}
    body.has-photo-bg .player-section {{
      background: transparent;
      backdrop-filter: none;
    }}
    body.has-photo-bg .wave-wrap,
    body.has-photo-bg .volume-slider {{
      background: rgba(18, 26, 43, 0.82);
      backdrop-filter: blur(6px);
    }}
    """
    return "has-photo-bg", css


def _write_html(
    session,
    target_dir: Path,
) -> None:
    body_class, background_css = build_background_css(session.bg_landscape, session.bg_portrait)
    html = HTML_TEMPLATE.replace("__AUDIO_FILE__", session.audio.name)
    html = html.replace("__BODY_CLASS__", body_class)
    html = html.replace("__BACKGROUND_CSS__", background_css)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text(html, encoding="utf-8")


def build(session) -> None:
    if not session.results_path.exists():
        raise SystemExit(f"Missing results file: {session.results_path}. Run analyze.py first.")

    if bool(session.bg_landscape) ^ bool(session.bg_portrait):
        raise SystemExit("Provide both landscape and portrait backgrounds, or neither.")

    _write_html(session, session.root)
    print(f"Visualizer written to {session.index_html}")


def _copy_asset(source: Path, target_dir: Path) -> None:
    destination = target_dir / source.name
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def publish(session) -> None:
    build(session)

    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True)

    _write_html(session, DOCS_DIR)
    _copy_asset(session.results_path, DOCS_DIR)
    _copy_asset(session.audio, DOCS_DIR)
    if session.bg_landscape and session.bg_portrait:
        _copy_asset(session.bg_landscape, DOCS_DIR)
        _copy_asset(session.bg_portrait, DOCS_DIR)

    print(f"Published to {DOCS_DIR}/")
    print("Push to GitHub, then enable Pages: branch main, folder /docs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", help="Recording session id (folder under sessions/)")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Copy session bundle to docs/ for GitHub Pages",
    )
    args = parser.parse_args()

    if not args.session:
        raise SystemExit("Provide --session <id>. Use 'python run.py --list' to see sessions.")

    session = load_session(args.session)
    if args.publish:
        publish(session)
    else:
        build(session)


if __name__ == "__main__":
    main()