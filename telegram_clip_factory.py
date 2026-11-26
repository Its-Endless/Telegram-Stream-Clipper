import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

TEXT_MODE  = "RELATABLE"  # "RELATABLE" or "NONE"
D_ROOT     = pathlib.Path(r"D:\Automation Youtube Clipping")
BASE       = D_ROOT / "data"
READY_DIR  = D_ROOT / "READY_TO_POST"
WATCHLIST  = D_ROOT / "watchlist.txt"
HISTORY    = BASE / "history.json"
PAUSE_FLAG = D_ROOT / "PAUSE.flag"
HOME_SC    = pathlib.Path.home() / "StreamClips"
SETTINGS_F = HOME_SC / "settings.json"

SEARCH_ROTATION = [
    ("GTA 6",     "gta 6,gta vi,gta6", "today", "GTA 6 live stream gameplay"),
    ("GTA 6",     "gta 6,gta vi,gta6", "week",  "GTA 6 gameplay stream"),
    ("Valorant",  "valorant",          "today", "Valorant live stream gameplay"),
    ("Minecraft", "minecraft",         "today", "Minecraft live stream gameplay"),
    ("BGMI",      "bgmi,pubg",         "week",  "BGMI live stream gameplay"),
    ("Fortnite",  "fortnite",          "today", "Fortnite live stream gameplay"),
    ("GTA 6",     "gta 6,gta vi,gta6", "month", "GTA 6 stream"),
    ("Valorant",  "valorant",          "week",  "Valorant stream"),
]

HYPE_WORDS = {
    "what", "bro", "omg", "wtf", "crazy", "insane", "holy", "die", "dead",
    "kill", "cops", "police", "run", "bhai", "kya", "arey", "pagal", "abe",
    "saale", "mar", "bachao", "ruk", "baap", "hatt", "haha", "lmao", "gta",
    "car", "op", "first", "finally", "look", "dekho"
}

def log(msg: str):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_valid_settings():
    HOME_SC.mkdir(parents=True, exist_ok=True)
    clean_cfg = {"min_score": 71, "clips": 20, "language": "en", "min_len": 30, "max_len": 90}
    if SETTINGS_F.exists():
        try:
            raw = SETTINGS_F.read_text(encoding="utf-8-sig").strip()
            existing = json.loads(raw) if raw else {}
            if isinstance(existing, dict):
                for k in ("min", "max", "min_sec", "max_sec"):
                    existing.pop(k, None)
                existing.update(clean_cfg)
                SETTINGS_F.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                return
        except Exception:
            pass
    SETTINGS_F.write_text(json.dumps(clean_cfg, indent=2), encoding="utf-8")

def has_ytdlp(py_exe: str) -> bool:
    try:
        r = subprocess.run([py_exe, "-c", "import yt_dlp"], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False

def find_skill_path() -> pathlib.Path:
    home = pathlib.Path.home()
    for p in [
        D_ROOT / "engine" / "scripts" / "streamclips.py",
        home / ".gemini" / "skills" / "stream-clips" / "scripts" / "streamclips.py",
        home / "StreamClips" / "scripts" / "streamclips.py",
    ]:
        if p.exists():
            return p
    hits = list(D_ROOT.rglob("streamclips.py"))
    return hits[0] if hits else D_ROOT / "engine" / "scripts" / "streamclips.py"

def find_python_with_deps() -> str:
    home = pathlib.Path.home()
    candidates = [
        home / ".streamclips" / "Scripts" / "python.exe",
        D_ROOT / ".streamclips" / "Scripts" / "python.exe",
        pathlib.Path(sys.executable),
    ]
    existing = [str(p) for p in candidates if p.exists()]
    for py in existing:
        if has_ytdlp(py):
            return py
    return existing[0] if existing else sys.executable

SKILL = find_skill_path()
SC_PYTHON = find_python_with_deps()

def ensure_environment():
    global SC_PYTHON
    ensure_valid_settings()
    if has_ytdlp(SC_PYTHON):
        return
    if SKILL.exists():
        log("Running first-time 'streamclips.py setup'...")
        subprocess.run([sys.executable, str(SKILL), "setup"], check=False)
        SC_PYTHON = find_python_with_deps()
    if not has_ytdlp(SC_PYTHON):
        subprocess.run([SC_PYTHON, "-m", "pip", "install", "-U", "yt-dlp"], check=False)

def sleep_with_pause(seconds: int):
    end_t = time.time() + max(0, seconds)
    while True:
        if PAUSE_FLAG.exists():
            log("PAUSED (PAUSE.flag active). Tap Start in Telegram to resume...")
            while PAUSE_FLAG.exists():
                time.sleep(2)
            log("RESUMED! Telegram Clip Factory is active again.")
        rem = end_t - time.time()
        if rem <= 0:
            break
        time.sleep(min(2.0, rem))

def clean_bloat():
    for cache_dir in [BASE / ".cache", HOME_SC / ".cache"]:
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
    for junk in D_ROOT.rglob("*.bak"):
        try:
            junk.unlink()
        except Exception:
            pass

def extract_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else url.strip()

def load_history() -> dict:
    if HISTORY.exists():
        try:
            data = json.loads(HISTORY.read_text(encoding="utf-8-sig"))
            cv = data.get("clipped_videos", {})
            data["clipped_videos"] = {k: v for k, v in cv.items() if v.get("success")}
            return data
        except Exception:
            pass
    return {"clipped_videos": {}}

def save_history(data: dict):
    BASE.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def ensure_watchlist():
    if not WATCHLIST.exists():
        WATCHLIST.write_text("# Add YouTube @handles or stream URLs (one per line):\n", encoding="utf-8")

def get_watchlist_entries():
    ensure_watchlist()
    urls, handles = [], []
    for raw in WATCHLIST.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        target = line.split("|")[0].strip()
        if target.startswith("http"):
            urls.append(target)
        elif target.startswith("youtube:@"):
            handles.append(target.split(":", 1)[1].strip())
        elif target.startswith("@"):
            handles.append(target)
    return urls, handles

def to_sec(tok: str) -> float:
    tok = tok.strip().rstrip("sS")
    if ":" in tok:
        p = [float(x) for x in tok.split(":")]
        return p[0] * 3600.0 + p[1] * 60.0 + p[2] if len(p) == 3 else p[0] * 60.0 + p[1]
    return float(tok)

def make_relatable_title(creator: str, vcontext: str, vb: float, cb: float, idx: int) -> str:
    if TEXT_MODE.upper() == "NONE":
        return ""
    who = creator.strip() if creator and creator.lower() not in ("creator", "na") else vcontext
    if vb >= 7.0 or cb >= 2.0:
        pool = [f"{who} Lost His Mind in {vcontext}!", f"{who} Insane {vcontext} Reaction!",
                f"Unbelievable {vcontext} Moment by {who}!", f"{who} Could Not Believe This in {vcontext}!"]
    elif vb >= 4.0:
        pool = [f"{who} Crazy {vcontext} Gameplay!", f"{who} Funny {vcontext} Moment!",
                f"Watch {who} Go Wild in {vcontext}!", f"{who} Best {vcontext} Highlight!"]
    else:
        pool = [f"{who} {vcontext} Highlight!", f"{who} Epic {vcontext} Clip!",
                f"{who} Playing {vcontext}!", f"{who} Viral {vcontext} Moment!"]
    return pool[idx % len(pool)][:58]

def score_part(pf: pathlib.Path, creator: str, vcontext: str, total_parts: int, p_idx: int):
    txt = pf.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"part_(\d+)", pf.name)
    off = float(int(m.group(1))) if m else float(p_idx * 580)
    lines = txt.splitlines()
    ts_re = re.compile(r"^\s*[\[\(]?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?|\d+(?:\.\d+)?)s?\b")
    rows = []
    for i, l in enumerate(lines):
        if any(k in l for k in ('"start"', '"score"', '"title"', '"hashtags"', "JSON", "Return")):
            continue
        mt = ts_re.search(l)
        if mt:
            try:
                rows.append((i, to_sec(mt.group(1))))
            except ValueError:
                pass
    rel = bool(rows and off >= 500 and rows[0][1] < off * 0.5)
    cands = []
    ctag = "#" + (re.sub(r"[^A-Za-z0-9]", "", creator) or "Streamer")
    vtag = "#" + (re.sub(r"[^A-Za-z0-9]", "", vcontext) or "Gaming")

    for i, rsec in rows:
        sec = rsec + (off if rel else 0.0)
        if sec < 15.0:
            continue
        win = "\n".join(lines[max(0, i - 2):min(len(lines), i + 8)])
        vb = max([float(x) for x in re.findall(r"<<VOLUME\s*\+?(\d+(?:\.\d+)?)\s*dB>>", win, re.I)] or [0.0])
        cb = max([float(x) for x in re.findall(r"<<CHAT\s*(\d+(?:\.\d+)?)x>>", win, re.I)] or [1.0])
        raw_lines = [l for l in lines[i:min(len(lines), i + 6)] if '"start"' not in l]
        cleaned = []
        for l in raw_lines:
            l = re.sub(r"\[[^\]]+\]", "", l)
            l = re.sub(r"<<[^>]+>>", "", l)
            l = re.sub(r"^\s*\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?s?\s*[-\u2013:]?\s*", "", l)
            cleaned.append(l.strip(" :-"))
        q = re.sub(r"\s+", " ", " ".join(cleaned)).strip(" .,!?:;-")
        if len(q) < 4:
            continue
        words = set(re.findall(r"[a-z]+", q.lower()))
        hype = len(words & HYPE_WORDS) + q.count("!") + q.count("?")
        bonus = 4 if (total_parts > 1 and p_idx >= total_parts // 3) else 0
        sc = int(min(99, max(45, 50 + vb * 2.4 + (cb - 1.0) * 4.8 + hype * 2.2 + bonus)))
        if sc <= 70:
            continue
        engagement = min(1.0, max(0.0, (sc - 70) / 28.0))
        dur = round(30.0 + engagement * 60.0, 1)
        lead_in = 6.0 if dur >= 50.0 else 4.0
        st = max(10.0, sec - lead_in)
        cands.append({
            "start": round(st, 1),
            "end": round(st + dur, 1),
            "type": "reaction" if vb >= 4.0 else "funny",
            "title": make_relatable_title(creator, vcontext, vb, cb, len(cands) + p_idx),
            "caption": f"{creator} {vcontext} highlight - watch till the end!",
            "hashtags": [vtag, ctag, "#Shorts"],
            "score": sc,
            "why": f"Score {sc}/100 ({int(dur)}s) at {int(st // 60)}m{int(st % 60):02d}s (+{vb:.1f} dB, {cb:.1f}x chat).",
        })

    cands.sort(key=lambda x: x["score"], reverse=True)
    kept = []
    for c in cands:
        if all(min(c["end"], k["end"]) - max(c["start"], k["start"]) <= 5.0 for k in kept):
            kept.append(c)
    return kept

def resolve_prompts(prompt_paths, creator: str, vcontext: str):
    targets = set(pathlib.Path(p) for p in prompt_paths if os.path.exists(p))
    if not targets:
        for cdir in [BASE / ".cache", HOME_SC / ".cache"]:
            if cdir.exists():
                for root, _, files in os.walk(str(cdir)):
                    for f in files:
                        if f.startswith("part_") and f.endswith(".prompt.txt"):
                            targets.add(pathlib.Path(root) / f)
    sorted_t = sorted(targets)
    for idx, pf in enumerate(sorted_t):
        af = pf.with_name(pf.name.replace(".prompt.txt", ".answer.json"))
        picks = score_part(pf, creator, vcontext, len(sorted_t), idx)
        af.write_text(json.dumps(picks, indent=2, ensure_ascii=False), encoding="utf-8")

def run_sc(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    out = []
    for line in p.stdout:
        print(line, end="", flush=True)
        out.append(line.strip())
    p.wait()
    return p.returncode, out

def ytdlp_direct_search(query: str, clipped_ids: dict, max_results: int = 12):
    cmd = [SC_PYTHON, "-m", "yt_dlp", "--flat-playlist", "--no-warnings",
           "--print", "%(id)s\t%(duration)s\t%(channel,uploader)s\t%(title)s", f"ytsearch{max_results}:{query}"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    found = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        vid, dur_s, channel, title = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        if not re.match(r"^[A-Za-z0-9_-]{11}$", vid) or vid in clipped_ids:
            continue
        try:
            dur = float(dur_s)
        except ValueError:
            dur = 0.0
        if 900 <= dur <= 28800:
            url = f"https://www.youtube.com/watch?v={vid}"
            clean_ch = "Creator" if channel in ("", "NA", "None") else channel
            found.append((vid, url, clean_ch, f"{clean_ch} - {title}"))
    return found

def find_unclipped(topic: str, keywords: str, when: str, raw_query: str, clipped_ids: dict):
    found, seen = [], set()
    w_urls, w_handles = get_watchlist_entries()
    for url in w_urls:
        vid = extract_video_id(url)
        if vid not in clipped_ids and vid not in seen:
            seen.add(vid)
            found.append((vid, url, "Watchlist", url))
    for handle in w_handles[:4]:
        cmd = [SC_PYTHON, "-m", "yt_dlp", "--flat-playlist", "--playlist-end", "4", "--no-warnings",
               "--print", "%(id)s\t%(duration)s\t%(channel,uploader)s\t%(title)s", f"https://www.youtube.com/{handle}/streams"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                vid, dur_s, ch, ttl = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
                try:
                    dur = float(dur_s)
                except ValueError:
                    dur = 0.0
                if re.match(r"^[A-Za-z0-9_-]{11}$", vid) and vid not in clipped_ids and vid not in seen and dur >= 900:
                    seen.add(vid)
                    clean_ch = handle if ch in ("", "NA", "None") else ch
                    found.append((vid, f"https://www.youtube.com/watch?v={vid}", clean_ch, f"{clean_ch} - {ttl}"))
    if found:
        return found
    if SKILL.exists():
        cmd = [SC_PYTHON, str(SKILL), "find", "--topic", topic, "--keywords", keywords, "--when", when]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        label = ""
        for l in res.stdout.splitlines():
            s = l.strip()
            if re.match(r"^\d+\.\s+", s):
                label = s
            elif "http" in s:
                m_u = re.search(r"https?://\S+", s)
                if m_u:
                    url = m_u.group(0)
                    vid = extract_video_id(url)
                    if vid not in clipped_ids and vid not in seen:
                        seen.add(vid)
                        raw_name = re.sub(r"^\d+\.\s+", "", label)
                        creator = re.split(r"\s{2,}", raw_name)[0].strip() if raw_name else "Creator"
                        found.append((vid, url, creator, label or url))
    if not found:
        for item in ytdlp_direct_search(raw_query, clipped_ids):
            if item[0] not in seen:
                seen.add(item[0])
                found.append(item)
    return found

def stage_all_ready_clips(out_dir: pathlib.Path, url: str, creator: str, orig_title: str, topic: str) -> int:
    READY_DIR.mkdir(parents=True, exist_ok=True)
    cj = out_dir / "clips.json"
    raw = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    clips = raw if isinstance(raw, list) else raw.get("clips", [])
    meta_by_file = {c.get("file") or c.get("filename"): c for c in clips if (c.get("file") or c.get("filename"))}

    safe_creator = re.sub(r"[^A-Za-z0-9_-]", "", creator) or "Creator"
    ctag = f"#{safe_creator}"
    vtag = "#" + (re.sub(r"[^A-Za-z0-9]", "", topic) or "Gaming")

    staged = 0
    for mp4_path in sorted(out_dir.glob("*.mp4")):
        c = meta_by_file.get(mp4_path.name, {})
        score = float(c.get("score", 75))
        if score <= 70:
            continue
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_mp4 = READY_DIR / f"{stamp}_{safe_creator}_{mp4_path.name}"
        shutil.copy2(mp4_path, dest_mp4)

        title = (c.get("title") or f"{creator} {topic} Highlight!").strip()[:60]
        cap = (c.get("caption") or f"{creator} playing {topic} - watch till the end!").strip()
        tags = " ".join(c.get("hashtags") or []) or f"{vtag} {ctag} #GamingClips #Shorts"

        post_txt = "\n".join([
            f"VIDEO FILE: {dest_mp4.name}",
            "VISIBILITY: Public (Review clip & creator permission before publishing)",
            f"TITLE:      {title}",
            "",
            "DESCRIPTION & CREDITS (Copy-Paste into YouTube Studio):",
            "------------------------------------------------------------",
            cap,
            f'Watch {creator} in "{orig_title}" - rate this moment 1-10!',
            "",
            f"Original Creator: {creator}",
            f"Full Video Link:  {url}",
            tags,
            "------------------------------------------------------------",
        ])
        dest_mp4.with_suffix(".txt").write_text(post_txt, encoding="utf-8")
        log(f"QUEUED FOR TELEGRAM (Score {int(score)}): {dest_mp4.name}")
        staged += 1
        time.sleep(1)
    return staged

def process_one_stream(vid: str, url: str, creator_hint: str, label: str, topic: str) -> int:
    if not SKILL.exists():
        log(f"[ERROR] Cannot find streamclips.py at {SKILL}")
        return 0
    ensure_valid_settings()
    t0 = time.time() - 2.0
    cmd = [SC_PYTHON, str(SKILL), "clip", url, "--topic", topic, "--layout", "stack",
           "--clips", "20", "--min", "30", "--max", "90", "--language", "en", "--fast", "--brain", "agent"]
    rc, lines1 = run_sc(cmd + ["--repick"])
    if rc not in (0, 3):
        rc, lines1 = run_sc(cmd + ["--repick", "--cookies", "chrome"])

    creator, orig_title, prompt_paths = creator_hint, label, []
    for l in lines1:
        mc = re.match(r"^\[\d+:\d+\]\s+[+>]\s+([^:]+):\s+(?:downloading|reusing|audio ready|listening)", l)
        if mc:
            creator = mc.group(1).strip()
        mt = re.match(r"^\[\d+:\d+\]\s+\+\s+([^:]+):\s+(.+?)\s+\(\d+[hm]", l)
        if mt:
            creator = mt.group(1).strip()
            orig_title = mt.group(2).strip()
        if ".prompt.txt" in l:
            prompt_paths.append(l.strip())

    resolve_prompts(prompt_paths, creator, topic)
    run_sc(cmd)

    jsons = []
    for sroot in [d for d in [BASE, HOME_SC] if d.exists()]:
        for p in sroot.rglob("clips.json"):
            if p.stat().st_mtime >= t0:
                jsons.append(p)
    jsons.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    total_staged = 0
    for j in jsons:
        staged = stage_all_ready_clips(j.parent, url, creator, orig_title, topic)
        if staged > 0:
            total_staged += staged
            break
    clean_bloat()
    return total_staged

def main():
    clean_bloat()
    ensure_watchlist()
    READY_DIR.mkdir(parents=True, exist_ok=True)
    ensure_environment()
    print("=" * 68)
    print("  MODE 1: 24/7 TELEGRAM STREAM CLIP FACTORY (SCORE > 70 | 30-90s)")
    print(f"  Output Queue: {READY_DIR} -> telegram_bot_remote.py")
    print("=" * 68)

    rot_idx = 0
    try:
        while True:
            sleep_with_pause(0)
            topic, keywords, when, raw_query = SEARCH_ROTATION[rot_idx % len(SEARCH_ROTATION)]
            rot_idx += 1
            history = load_history()
            clipped_ids = history.setdefault("clipped_videos", {})
            candidates = find_unclipped(topic, keywords, when, raw_query, clipped_ids)
            if not candidates:
                sleep_with_pause(10)
                continue
            for vid, url, creator_hint, label in candidates:
                sleep_with_pause(0)
                staged_count = 0
                try:
                    staged_count = process_one_stream(vid, url, creator_hint, label, topic)
                except Exception as e:
                    log(f"[ERROR] {vid}: {e}")
                    clean_bloat()
                if staged_count > 0:
                    history = load_history()
                    history.setdefault("clipped_videos", {})[vid] = {
                        "url": url, "creator": creator_hint, "title": label,
                        "clips_created": staged_count,
                        "clipped_at": datetime.datetime.now().isoformat(timespec="seconds"),
                        "success": True,
                    }
                    save_history(history)
                    sleep_with_pause(5)
                else:
                    sleep_with_pause(5)
    except KeyboardInterrupt:
        clean_bloat()
        log("Stopped by user.")

if __name__ == "__main__":
    main()