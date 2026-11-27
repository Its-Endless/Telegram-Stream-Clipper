import datetime
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

D_ROOT     = pathlib.Path(r"D:\Automation Youtube Clipping")
WORK_DIR   = D_ROOT / "data" / "video_shorts_work"
OUTPUT_DIR = D_ROOT / "VIDEO_SHORTS"

HYPE_WORDS = {
    "what", "bro", "omg", "wtf", "crazy", "insane", "holy", "secret", "truth",
    "never", "always", "best", "worst", "unbelievable", "shocking", "reason",
    "why", "how", "mistake", "hack", "tip", "trick", "bhai", "kya", "arey",
    "pagal", "dekho", "sach", "raaz", "amazing", "epic", "finally", "first",
    "biggest", "hidden", "watch", "wait", "stop", "listen", "look", "legendary"
}

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "you", "are", "was", "were",
    "have", "has", "had", "not", "but", "what", "when", "where", "who", "why",
    "how", "all", "any", "both", "each", "more", "most", "other", "some", "such",
    "than", "too", "very", "can", "will", "just", "should", "now", "video", "bro",
    "bhai", "hai", "nahi", "kya", "mein", "aur", "se", "ko", "ka", "ki", "ke"
}

def log(msg: str):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def has_ytdlp(py_exe: str) -> bool:
    try:
        r = subprocess.run([py_exe, "-c", "import yt_dlp"], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False

def find_python_with_deps() -> str:
    home = pathlib.Path.home()
    candidates = [
        home / ".streamclips" / "Scripts" / "python.exe",
        D_ROOT / ".streamclips" / "Scripts" / "python.exe",
        pathlib.Path(r"C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe"),
        pathlib.Path(sys.executable),
    ]
    existing = [str(p) for p in candidates if p.exists()]
    for py in existing:
        if has_ytdlp(py):
            return py
    return existing[0] if existing else sys.executable

def find_ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for root in [pathlib.Path.home() / ".streamclips", pathlib.Path(os.environ.get("LOCALAPPDATA", ""))]:
        if root.exists():
            for p in root.rglob("ffmpeg.exe"):
                return str(p)
    return "ffmpeg"

SC_PYTHON = find_python_with_deps()
FFMPEG_BIN = find_ffmpeg_bin()

def ensure_environment():
    if not has_ytdlp(SC_PYTHON):
        log("Installing yt-dlp...")
        subprocess.run([SC_PYTHON, "-m", "pip", "install", "-U", "yt-dlp"], check=False)

def clean_work():
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    for junk in D_ROOT.rglob("*.bak"):
        try:
            junk.unlink()
        except Exception:
            pass

def parse_timestamp_tokens(text: str, max_dur: float) -> list[float]:
    hits = []
    for m in re.finditer(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b", text):
        h = int(m.group(1)) if m.group(1) else 0
        mins = int(m.group(2))
        secs = int(m.group(3))
        if mins >= 60 or secs >= 60:
            continue
        total = h * 3600.0 + mins * 60.0 + secs
        if 3.0 <= total <= max(10.0, max_dur - 10.0):
            hits.append(total)
    return hits

def fetch_metadata_and_comments(url: str) -> dict:
    log("Reading video metadata & viewer comments...")
    cmd = [
        SC_PYTHON, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "--dump-single-json",
        "--write-comments",
        "--extractor-args", "youtube:max_comments=150,all,100;comment_sort=top",
        url,
    ]
    info = {}
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        for line in reversed(res.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                info = json.loads(line)
                break
    except Exception as e:
        log(f"Metadata/comments warning: {e}")

    title = str(info.get("title") or "YouTube Video").strip()
    creator = str(info.get("channel") or info.get("uploader") or "Creator").strip()
    duration = float(info.get("duration") or 0.0)
    comments = info.get("comments") or []
    heatmap = info.get("heatmap") or []

    ts_boosts = []
    word_weights = {}

    for c in comments:
        txt = str(c.get("text") or "")
        likes = int(c.get("like_count") or 0)
        weight = 1.0 + math.log1p(max(0, likes))

        for t_sec in parse_timestamp_tokens(txt, duration or 36000.0):
            ts_boosts.append((t_sec, weight))

        for w in re.findall(r"[a-zA-Z]{3,}", txt.lower()):
            if w not in STOPWORDS:
                word_weights[w] = word_weights.get(w, 0.0) + min(weight, 5.0)

    top_comment_words = {
        w for w, _ in sorted(word_weights.items(), key=lambda kv: kv[1], reverse=True)[:45]
    }

    heatmap_peaks = []
    for seg in heatmap:
        val = float(seg.get("value") or 0.0)
        st = float(seg.get("start_time") or 0.0)
        if val >= 0.65 and st >= 3.0:
            heatmap_peaks.append((st, val))

    log(
        f"Analyzed {len(comments)} comment(s) -> {len(ts_boosts)} timestamp mention(s), "
        f"{len(top_comment_words)} top comment keyword(s), {len(heatmap_peaks)} replay peak(s)."
    )
    return {
        "title": title,
        "creator": creator,
        "duration": duration,
        "ts_boosts": ts_boosts,
        "top_comment_words": top_comment_words,
        "heatmap_peaks": heatmap_peaks,
    }

def download_audio_track(url: str, audio_out: pathlib.Path) -> bool:
    log("Downloading audio track for speech & energy analysis...")
    cmd = [
        SC_PYTHON, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "-f", "bestaudio/best",
        "-o", str(audio_out),
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if r.returncode == 0 and audio_out.exists() and audio_out.stat().st_size > 1000:
        return True
    r2 = subprocess.run(cmd[:3] + ["--cookies", "chrome"] + cmd[3:], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return r2.returncode == 0 and audio_out.exists() and audio_out.stat().st_size > 1000

def get_media_duration(media_path: pathlib.Path) -> float:
    probe = subprocess.run([FFMPEG_BIN, "-i", str(media_path)], capture_output=True, text=True, errors="replace", check=False)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    if m:
        return int(m.group(1)) * 3600.0 + int(m.group(2)) * 60.0 + float(m.group(3))
    return 0.0

def measure_audio_loudness_timeline(audio_path: pathlib.Path) -> dict[int, float]:
    cmd = [
        FFMPEG_BIN, "-hide_banner", "-i", str(audio_path),
        "-af", "asetnsamples=n=44100:p=1,astats=metadata=1:reset=1",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False)
    rms_vals = []
    for m in re.finditer(r"RMS level dB:\s*(-?\d+(?:\.\d+)?|-inf)", res.stderr):
        raw = m.group(1)
        rms_vals.append(-90.0 if raw == "-inf" else float(raw))

    if not rms_vals:
        return {}
    valid = [v for v in rms_vals if v > -85.0]
    avg_db = (sum(valid) / len(valid)) if valid else -30.0
    return {sec_idx: max(0.0, db - avg_db) for sec_idx, db in enumerate(rms_vals)}

def transcribe_segments(audio_path: pathlib.Path) -> list[dict]:
    whisper_script = (
        "import json, sys\n"
        "audio_file = sys.argv[1]\n"
        "segs = []\n"
        "try:\n"
        "    from faster_whisper import WhisperModel\n"
        "    model = WhisperModel('tiny', device='cpu', compute_type='int8')\n"
        "    raw_segs, _ = model.transcribe(audio_file, vad_filter=True)\n"
        "    for s in raw_segs:\n"
        "        segs.append({'start': float(s.start), 'end': float(s.end), 'text': s.text.strip()})\n"
        "except Exception:\n"
        "    try:\n"
        "        import whisper\n"
        "        model = whisper.load_model('tiny')\n"
        "        res = model.transcribe(audio_file, fp16=False)\n"
        "        for s in res.get('segments', []):\n"
        "            segs.append({'start': float(s['start']), 'end': float(s['end']), 'text': s['text'].strip()})\n"
        "    except Exception:\n"
        "        pass\n"
        "print(json.dumps(segs))\n"
    )
    try:
        res = subprocess.run(
            [SC_PYTHON, "-c", whisper_script, str(audio_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
        for line in reversed(res.stdout.splitlines()):
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                return json.loads(line)
    except Exception as e:
        log(f"Transcription fallback active: {e}")
    return []

def build_guaranteed_clips(duration: float, meta: dict, loudness: dict[int, float], segments: list[dict]) -> list[dict]:
    if duration <= 62.0:
        end_t = max(8.0, duration - 0.2)
        return [{"start": 0.0, "end": round(end_t, 2), "score": 85.0, "reason": "Full video adapted to 9:16 Short"}]

    target_count = min(10, max(2, int(duration // 150) + 2))
    clip_len = min(56.0, max(28.0, duration * 0.18))
    ts_boosts = meta["ts_boosts"]
    top_words = meta["top_comment_words"]
    heatmap_peaks = meta["heatmap_peaks"]

    candidates = []

    for idx, seg in enumerate(segments):
        st = max(2.0, float(seg["start"]) - 2.5)
        if st + 20.0 > duration:
            continue
        win_txt = " ".join(
            s["text"] for s in segments[idx:min(len(segments), idx + 8)]
            if float(s["start"]) <= st + clip_len
        )
        words = set(re.findall(r"[a-z]{3,}", win_txt.lower()))
        hype_hits = len(words & HYPE_WORDS) + win_txt.count("!") + win_txt.count("?")
        comment_word_hits = len(words & top_words)

        comment_ts_score = 0.0
        for c_sec, weight in ts_boosts:
            if abs(c_sec - (st + clip_len * 0.4)) <= 18.0:
                comment_ts_score += 18.0 * min(weight, 3.0)

        heat_score = 0.0
        for h_sec, h_val in heatmap_peaks:
            if st <= h_sec <= st + clip_len:
                heat_score = max(heat_score, h_val * 25.0)

        peak_db = max([loudness.get(s, 0.0) for s in range(int(st), min(int(duration), int(st + clip_len)))] or [0.0])

        score = (
            40.0
            + min(35.0, comment_ts_score)
            + min(20.0, comment_word_hits * 4.5)
            + heat_score
            + peak_db * 2.8
            + hype_hits * 2.4
        )
        end_t = min(duration - 0.5, st + clip_len)
        if end_t - st >= 18.0:
            candidates.append({
                "start": round(st, 2),
                "end": round(end_t, 2),
                "score": round(score, 1),
                "reason": f"CommentTS:{comment_ts_score:.0f} | CommentKw:{comment_word_hits} | Peak:+{peak_db:.1f}dB",
            })

    for c_sec, weight in ts_boosts:
        st = max(2.0, min(duration - clip_len - 0.5, c_sec - 6.0))
        end_t = min(duration - 0.5, st + clip_len)
        if end_t - st >= 18.0:
            candidates.append({
                "start": round(st, 2),
                "end": round(end_t, 2),
                "score": round(72.0 + min(26.0, weight * 8.0), 1),
                "reason": f"Viewer comment timestamp ({int(c_sec // 60)}:{int(c_sec % 60):02d})",
            })

    for h_sec, h_val in heatmap_peaks:
        st = max(2.0, min(duration - clip_len - 0.5, h_sec - 5.0))
        end_t = min(duration - 0.5, st + clip_len)
        if end_t - st >= 18.0:
            candidates.append({
                "start": round(st, 2),
                "end": round(end_t, 2),
                "score": round(68.0 + h_val * 28.0, 1),
                "reason": f"Most-replayed peak ({int(h_val * 100)}%)",
            })

    step = max(15.0, clip_len * 0.75)
    t = 4.0
    while t + 20.0 < duration:
        end_t = min(duration - 0.5, t + clip_len)
        peak_db = max([loudness.get(s, 0.0) for s in range(int(t), min(int(duration), int(end_t)))] or [0.0])
        candidates.append({
            "start": round(t, 2),
            "end": round(end_t, 2),
            "score": round(42.0 + peak_db * 3.2, 1),
            "reason": f"Audio energy window (+{peak_db:.1f}dB)",
        })
        t += step

    candidates.sort(key=lambda x: x["score"], reverse=True)
    chosen = []
    for c in candidates:
        if all(min(c["end"], k["end"]) - max(c["start"], k["start"]) <= 5.0 for k in chosen):
            chosen.append(c)
            if len(chosen) >= target_count:
                break

    if not chosen:
        st = max(0.0, (duration - clip_len) * 0.35)
        end_t = min(duration - 0.2, st + clip_len)
        chosen.append({"start": round(st, 2), "end": round(end_t, 2), "score": 60.0, "reason": "Guaranteed highlight cut"})

    chosen.sort(key=lambda x: x["start"])
    return chosen

def download_full_video_fallback(url: str) -> pathlib.Path | None:
    full_mp4 = WORK_DIR / "full_source_video.mp4"
    if full_mp4.exists() and full_mp4.stat().st_size > 10000:
        return full_mp4
    log("Downloading full video source for reliable local slicing...")
    cmd = [
        SC_PYTHON, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", str(full_mp4),
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode != 0 or not full_mp4.exists():
        subprocess.run(cmd[:3] + ["--cookies", "chrome"] + cmd[3:], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    return full_mp4 if (full_mp4.exists() and full_mp4.stat().st_size > 10000) else None

def render_clean_9x16_short(url: str, start_sec: float, end_sec: float, out_mp4: pathlib.Path, idx: int) -> bool:
    raw_seg = WORK_DIR / f"raw_seg_{idx}.mp4"
    raw_seg.unlink(missing_ok=True)

    sec_spec = f"*{start_sec:.2f}-{end_sec:.2f}"
    dl_cmd = [
        SC_PYTHON, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--download-sections", sec_spec,
        "--force-keyframes-at-cuts",
        "-o", str(raw_seg),
        url,
    ]
    r = subprocess.run(dl_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if r.returncode != 0 or not raw_seg.exists() or raw_seg.stat().st_size < 10000:
        r2 = subprocess.run(dl_cmd[:3] + ["--cookies", "chrome"] + dl_cmd[3:], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        if r2.returncode != 0 or not raw_seg.exists() or raw_seg.stat().st_size < 10000:
            full_src = download_full_video_fallback(url)
            if full_src is None:
                return False
            dur = max(5.0, end_sec - start_sec)
            subprocess.run(
                [FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{start_sec:.2f}", "-i", str(full_src), "-t", f"{dur:.2f}",
                 "-c", "copy", str(raw_seg)],
                check=False
            )

    if not raw_seg.exists() or raw_seg.stat().st_size < 10000:
        return False

    vf = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
    )
    ff_cmd = [
        FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(raw_seg),
        "-filter_complex", vf,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    ff_res = subprocess.run(ff_cmd, capture_output=True, text=True, errors="replace", check=False)
    raw_seg.unlink(missing_ok=True)
    return ff_res.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 10000

def process_video_url(url: str) -> int:
    clean_work()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    meta = fetch_metadata_and_comments(url)
    title = meta["title"]
    creator = meta["creator"]
    duration = meta["duration"]

    log(f"Video:   {title}")
    log(f"Channel: {creator}")

    audio_file = WORK_DIR / "source_audio.m4a"
    has_audio = download_audio_track(url, audio_file)

    if duration <= 0 and has_audio:
        duration = get_media_duration(audio_file)
    if duration <= 0:
        duration = 180.0

    loudness = measure_audio_loudness_timeline(audio_file) if has_audio else {}
    segments = transcribe_segments(audio_file) if has_audio else []
    log(f"Transcribed {len(segments)} speech segment(s) | Duration: {int(duration // 60)}m{int(duration % 60):02d}s")

    picks = build_guaranteed_clips(duration, meta, loudness, segments)
    log(f"Generating {len(picks)} clean 9:16 Short(s) (NO captions | NO top hook title bar)...")

    safe_creator = re.sub(r"[^A-Za-z0-9_-]", "", creator) or "Creator"
    creator_dir = OUTPUT_DIR / safe_creator
    creator_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for idx, p in enumerate(picks, start=1):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_mp4 = creator_dir / f"{stamp}_short_{idx:02d}.mp4"
        log(f"[{idx}/{len(picks)}] Cutting {p['start']}s -> {p['end']}s ({p['reason']})...")
        if render_clean_9x16_short(url, p["start"], p["end"], out_mp4, idx):
            log(f"SAVED CLEAN SHORT: {out_mp4}")
            saved += 1
            time.sleep(1)

    clean_work()
    return saved

def main():
    ensure_environment()
    print("=" * 68)
    print("  CLEAN VIDEO-TO-SHORTS GENERATOR")
    print("  * Pure 9:16 Vertical (NO Captions | NO Top Hook Title Bar)")
    print("  * Comment-Calibrated + Audio/Speech Scoring (Always Generates Clips)")
    print(f"  * Output Folder: {OUTPUT_DIR}\\<Channel>\\")
    print("=" * 68)

    while True:
        print()
        try:
            raw_url = input("Paste Video URL (or 'q' to quit): ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not raw_url:
            continue
        if raw_url.lower() in ("q", "quit", "exit"):
            break
        if not raw_url.startswith("http"):
            print("[!] Please paste a valid http/https video link.")
            continue

        print("-" * 68)
        count = process_video_url(raw_url)
        print("-" * 68)
        print(f"[DONE] Saved {count} clean Short(s) inside: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()