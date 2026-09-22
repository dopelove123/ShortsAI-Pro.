from flask import Flask, request, jsonify, send_file, send_from_directory
import shutil
import os
import yt_dlp
from pathlib import Path
import tempfile
import uuid
import re
import threading
import imageio_ffmpeg

app = Flask(__name__)
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "shortsai_yt_downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def find_js_runtime():
    """Prefer local Deno, then Node. yt-dlp currently needs a JS runtime for full YouTube support."""
    candidates = []
    local_deno = Path(__file__).parent / "tools" / "deno.exe"
    if local_deno.exists():
        candidates.append(("deno", str(local_deno)))
    for exe, name in [("deno", "deno"), ("node", "node")]:
        p = shutil.which(exe)
        if p:
            candidates.append((name, p))
    return candidates[0] if candidates else (None, None)

def build_ydl_options(base):
    runtime_name, runtime_path = find_js_runtime()
    if runtime_name:
        base["js_runtimes"] = {runtime_name: {"path": runtime_path}}
    # Allow yt-dlp to fetch its EJS challenge scripts when needed.
    base["remote_components"] = ["ejs:github"]
    # imageio-ffmpeg ships a self-contained ffmpeg binary, so the user does not
    # need to install FFmpeg separately for MP4 merging or MP3 extraction.
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe:
            base["ffmpeg_location"] = ffmpeg_exe
    except Exception:
        pass
    return base

def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name or 'YouTube_Download')
    return name[:150].strip() or "YouTube_Download"

def quality_format(quality: str, audio_only: bool) -> str:
    if audio_only:
        return "bestaudio/best"

    if quality == "best":
        # Prefer the highest-FPS video-only stream, then merge the best audio.
        # Using bestvideo (instead of bestvideo*) avoids accidentally choosing
        # a lower-FPS progressive stream when a higher-FPS video-only stream exists.
        return "bestvideo+bestaudio/best"

    try:
        height = int(quality)
    except ValueError:
        height = 1080

    return (
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]/best"
    )

@app.get("/")
def home():
    response = send_from_directory(Path(__file__).parent, "ShortsAI_PRO_CREATOR_STUDIO_ULTRA_FINAL_NAV.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "ShortsAI YouTube Downloader"})

@app.post("/api/youtube/download")
def youtube_download():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    fmt = str(data.get("format", "mp4")).lower()
    quality = str(data.get("quality", "best"))

    if not url:
        return jsonify({"error": "YouTube URL is required."}), 400

    if not re.match(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", url, re.I):
        return jsonify({"error": "Please enter a valid YouTube URL."}), 400

    if fmt not in {"mp4", "mp3"}:
        return jsonify({"error": "Format must be MP4 or MP3."}), 400

    job = DOWNLOAD_DIR / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=True)

    audio_only = fmt == "mp3"

    opts = build_ydl_options({
        "outtmpl": str(job / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "restrictfilenames": True,
        "format": quality_format(quality, audio_only),
        # Explicitly prioritize resolution first and FPS second. yt-dlp documents
        # FPS as a format-sort field; forcing the order prevents a lower-FPS
        # progressive format from winning when a higher-FPS stream is available.
        "format_sort": ["res", "fps", "vcodec", "br"],
        "format_sort_force": True,
        "merge_output_format": "mp4" if not audio_only else None,
    })

    if audio_only:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            requested_title = safe_name(info.get("title", "YouTube_Download"))

        candidates = [p for p in job.iterdir() if p.is_file()]
        if not candidates:
            raise RuntimeError("Downloader finished but no output file was created.")

        # Prefer the requested extension when multiple files exist.
        wanted = [p for p in candidates if p.suffix.lower() == "." + fmt]
        output = wanted[0] if wanted else candidates[0]

        download_name = requested_title + output.suffix.lower()

        response = send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype="audio/mpeg" if output.suffix.lower() == ".mp3" else "video/mp4",
        )

        def cleanup():
            try:
                shutil.rmtree(job, ignore_errors=True)
            except Exception:
                pass

        response.call_on_close(cleanup)
        return response

    except Exception as exc:
        shutil.rmtree(job, ignore_errors=True)
        message = str(exc).strip() or "Download failed."
        runtime_name, runtime_path = find_js_runtime()
        if not runtime_name:
            message += " | No supported JavaScript runtime found. Install Deno 2.3+ or Node 22+ and restart the server."
        return jsonify({"error": message}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"ShortsAI PRO server running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
