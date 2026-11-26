import datetime
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

D_ROOT         = pathlib.Path(r"D:\Automation Youtube Clipping")
READY_DIR      = D_ROOT / "READY_TO_POST"
SENT_DIR       = D_ROOT / "SENT_TO_TELEGRAM"
CONFIG_FILE    = D_ROOT / "telegram_config.json"
PAUSE_FLAG     = D_ROOT / "PAUSE.flag"
WATCHLIST_FILE = D_ROOT / "watchlist.txt"
FACTORY_SCRIPT = D_ROOT / "telegram_clip_factory.py"
PYTHON_EXE     = pathlib.Path(r"C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe")

SEND_DELAY_SECONDS = 5

def log(msg: str):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_requests():
    try:
        import requests  # noqa: F401
        return True
    except ImportError:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "requests"], check=False)
        return r.returncode == 0

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

def _rewind_files(files):
    if not files:
        return
    for _, fobj in files.items():
        if isinstance(fobj, tuple) and len(fobj) >= 2 and hasattr(fobj[1], "seek"):
            try:
                fobj[1].seek(0)
            except Exception:
                pass

def tg_call(bot_token: str, method: str, data: dict = None, files=None, timeout: int = 180) -> dict:
    import requests
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    net_attempts = 0
    while True:
        _rewind_files(files)
        try:
            resp = requests.post(url, data=data or {}, files=files, timeout=timeout)
            if resp.status_code == 413:
                return {"ok": False, "error_code": 413, "description": "Request Entity Too Large"}
            payload = resp.json()
            if payload.get("ok"):
                return payload
            retry_after = payload.get("parameters", {}).get("retry_after")
            if resp.status_code == 429 and retry_after:
                time.sleep(int(retry_after) + 2)
                continue
            log(f"Telegram API warning ({method}): {payload}")
            return payload
        except Exception as e:
            net_attempts += 1
            log(f"Telegram network warning ({method}) [attempt {net_attempts}]: {e}")
            if files and net_attempts >= 2:
                return {"ok": False, "error_code": 413, "description": f"Upload interrupted: {e}"}
            time.sleep(5)

def is_factory_running() -> bool:
    try:
        ps = (
            "foreach ($p in Get-CimInstance Win32_Process) { "
            "if ($p.CommandLine -like '*telegram_clip_factory.py*' -or $p.CommandLine -like '*streamclips.py*') { "
            "if ($p.CommandLine -notlike '*telegram_bot_remote.py*') { $p.ProcessId } } }"
        )
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        return bool(out)
    except Exception:
        return False

def start_factory_process() -> str:
    if PAUSE_FLAG.exists():
        PAUSE_FLAG.unlink(missing_ok=True)
    if is_factory_running():
        return "▶️ <b>Resumed!</b> Telegram Clip Factory is running."
    if FACTORY_SCRIPT.exists():
        py_bin = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable
        subprocess.Popen([py_bin, str(FACTORY_SCRIPT)], cwd=str(D_ROOT), creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(1.5)
        return "🚀 <b>Started!</b> Opened <code>telegram_clip_factory.py</code> on your laptop."
    return "⚠️ Cleared <code>PAUSE.flag</code>, but <code>telegram_clip_factory.py</code> was not found."

def stop_factory_process() -> str:
    PAUSE_FLAG.write_text("STOPPED_FROM_TELEGRAM\n", encoding="utf-8")
    try:
        ps = (
            "foreach ($p in Get-CimInstance Win32_Process) { "
            "if ($p.CommandLine -like '*telegram_clip_factory.py*' -or $p.CommandLine -like '*streamclips.py*') { "
            "if ($p.CommandLine -notlike '*telegram_bot_remote.py*') { "
            "Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue } } }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=15)
    except Exception:
        pass
    return "⏹️ <b>Stopped!</b> Closed the clipping factory and enabled Pause mode."

def build_menu_markup() -> str:
    return json.dumps({
        "inline_keyboard": [
            [{"text": "▶️ Start / Resume", "callback_data": "act_start"}, {"text": "⏸️ Pause All", "callback_data": "act_pause"}],
            [{"text": "⏹️ Stop Factory", "callback_data": "act_stop"}, {"text": "📊 Live Status", "callback_data": "act_status"}],
        ]
    })

def send_status_message(bot_token: str, chat_id: str, prefix: str = ""):
    paused = PAUSE_FLAG.exists()
    running = is_factory_running()
    ready_count = len([p for p in READY_DIR.glob("*.mp4") if not p.name.endswith("_tgdoc.mp4")]) if READY_DIR.exists() else 0
    sent_count = len(list(SENT_DIR.glob("*.mp4"))) if SENT_DIR.exists() else 0
    _, _, free_b = shutil.disk_usage("D:\\")
    free_gb = free_b / (1024 ** 3)
    state_txt = "⏸️ PAUSED" if paused else ("🟢 RUNNING 24/7 (Score > 70 | 30-90s)" if running else "🔴 STOPPED")

    msg = f"{prefix}\n\n" if prefix else ""
    msg += (
        f"📱 <b>LAPTOP CLIPPER REMOTE</b>\n"
        f"• <b>State:</b> {state_txt}\n"
        f"• <b>Queued to Send:</b> {ready_count} clip(s)\n"
        f"• <b>Total Sent to Phone:</b> {sent_count} clip(s)\n"
        f"• <b>D: Drive Free Space:</b> {free_gb:.1f} GB\n\n"
        f"💡 <i>Paste any YouTube stream link here to add it to your watchlist!</i>"
    )
    tg_call(bot_token, "sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "reply_markup": build_menu_markup()})

def handle_user_command(bot_token: str, chat_id: str, raw_text: str):
    txt = raw_text.strip()
    low = txt.lower()
    url_m = re.search(r"(https?://\S+)", txt)
    if url_m:
        url = url_m.group(1)
        WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = WATCHLIST_FILE.read_text(encoding="utf-8-sig") if WATCHLIST_FILE.exists() else ""
        with open(WATCHLIST_FILE, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(f"{url}\n")
        send_status_message(bot_token, chat_id, f"📥 <b>Added link to Watchlist!</b>\n<code>{html.escape(url)}</code>")
        return

    if low in ("/start", "/menu", "menu", "help", "/help"):
        send_status_message(bot_token, chat_id, "👋 <b>Remote Control Ready!</b> Tap a button below:")
    elif low in ("start", "/run", "run", "resume", "/resume", "play"):
        send_status_message(bot_token, chat_id, start_factory_process())
    elif low in ("pause", "/pause"):
        PAUSE_FLAG.write_text("PAUSED_FROM_TELEGRAM\n", encoding="utf-8")
        send_status_message(bot_token, chat_id, "⏸️ <b>Paused!</b> Both clipping and sending are paused.")
    elif low in ("stop", "/stop"):
        send_status_message(bot_token, chat_id, stop_factory_process())
    elif low in ("status", "/status", "progress", "/progress"):
        send_status_message(bot_token, chat_id)
    else:
        send_status_message(bot_token, chat_id, "Send <b>start</b>, <b>pause</b>, <b>stop</b>, <b>status</b>, or paste any stream link:")

def telegram_listener_loop(bot_token: str, allowed_chat_id: str):
    import requests
    offset = 0
    try:
        init_r = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", params={"timeout": 1}, timeout=10).json()
        for u in init_r.get("result", []):
            offset = u["update_id"] + 1
    except Exception:
        pass

    log("Telegram Remote Listener ACTIVE. Waiting for phone buttons/commands...")
    send_status_message(bot_token, allowed_chat_id, "🚀 <b>Phone Remote Connected!</b>")

    while True:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", params={"timeout": 40, "offset": offset}, timeout=50).json()
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    cid = str(cq["message"]["chat"]["id"])
                    if cid != allowed_chat_id:
                        continue
                    tg_call(bot_token, "answerCallbackQuery", data={"callback_query_id": cq["id"]})
                    action = cq.get("data", "")
                    if action in ("act_start", "act_pause", "act_stop", "act_status"):
                        handle_user_command(bot_token, cid, action.replace("act_", ""))
                elif "message" in upd:
                    msg = upd["message"]
                    cid = str(msg["chat"]["id"])
                    if cid == allowed_chat_id and "text" in msg:
                        handle_user_command(bot_token, cid, msg["text"])
        except Exception as e:
            log(f"Listener polling error: {e}")
            time.sleep(5)

def parse_sidecar_txt(txt_path: pathlib.Path, fallback_stem: str) -> dict:
    title = fallback_stem.replace("_", " ")[:95]
    description = "#Shorts #Gaming"
    if txt_path.exists():
        raw = txt_path.read_text(encoding="utf-8-sig", errors="replace")
        m_title = re.search(r"^TITLE:\s*(.+)$", raw, re.MULTILINE)
        if m_title:
            title = m_title.group(1).strip()
        parts = re.split(r"-{20,}", raw)
        description = parts[1].strip() if len(parts) >= 3 else raw.strip()
    if "#shorts" not in title.lower() and "#shorts" not in description.lower():
        description = f"{description}\n\n#Shorts".strip()
    return {"title": title[:100], "description": description[:4500]}

def find_ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in pathlib.Path(os.environ.get("LOCALAPPDATA", "")).rglob("ffmpeg.exe"):
        return str(p)
    return "ffmpeg"

def get_video_duration(ffmpeg_bin: str, src_mp4: pathlib.Path) -> float:
    probe = subprocess.run([ffmpeg_bin, "-i", str(src_mp4)], capture_output=True, text=True, errors="replace", check=False)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    return (int(m.group(1)) * 3600.0 + int(m.group(2)) * 60.0 + float(m.group(3))) if m else 75.0

def shrink_to_doc_limit(src_mp4: pathlib.Path, target_mb: float = 45.0) -> pathlib.Path:
    ffmpeg_bin = find_ffmpeg_bin()
    dur = get_video_duration(ffmpeg_bin, src_mp4)
    total_kbps = max(650, int((target_mb * 8192) / max(dur, 1.0)))
    video_kbps = max(500, total_kbps - 128)
    tmp_out = src_mp4.with_name(src_mp4.stem + "_tgdoc.mp4")
    subprocess.run([
        ffmpeg_bin, "-y", "-i", str(src_mp4),
        "-c:v", "libx264", "-b:v", f"{video_kbps}k", "-maxrate", f"{int(video_kbps * 1.15)}k",
        "-bufsize", f"{video_kbps * 2}k", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp_out),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return tmp_out

def send_clip_to_telegram(bot_token: str, chat_id: str, mp4_path: pathlib.Path, meta: dict):
    size_mb = mp4_path.stat().st_size / (1024 * 1024)
    esc_title = html.escape(meta["title"])
    esc_desc  = html.escape(meta["description"])
    full_caption = f"🎬 <b>TITLE (Tap to copy):</b>\n<code>{esc_title}</code>\n\n📝 <b>DESCRIPTION &amp; HASHTAGS (Tap to copy):</b>\n<pre>{esc_desc}</pre>"

    if size_mb <= 48.5:
        with open(mp4_path, "rb") as f:
            if len(full_caption) <= 1024:
                res = tg_call(bot_token, "sendVideo", data={"chat_id": chat_id, "caption": full_caption, "parse_mode": "HTML", "supports_streaming": "true"}, files={"video": (mp4_path.name, f, "video/mp4")}, timeout=300)
            else:
                res = tg_call(bot_token, "sendVideo", data={"chat_id": chat_id, "caption": f"🎬 <b>TITLE (Tap to copy):</b>\n<code>{esc_title}</code>"[:1024], "parse_mode": "HTML", "supports_streaming": "true"}, files={"video": (mp4_path.name, f, "video/mp4")}, timeout=300)
                if res.get("ok"):
                    tg_call(bot_token, "sendMessage", data={"chat_id": chat_id, "text": f"📝 <b>DESCRIPTION &amp; HASHTAGS (Tap to copy):</b>\n<pre>{esc_desc}</pre>"[:4096], "parse_mode": "HTML", "disable_web_page_preview": "true"})
        if not res.get("ok"):
            raise RuntimeError(f"sendVideo failed: {res}")
        return

    log(f"Clip is {size_mb:.1f} MB (>50 MB Telegram Bot API cap) -> fitting to ~45 MB Document...")
    tmp_doc = shrink_to_doc_limit(mp4_path, target_mb=45.0)
    doc_mb = tmp_doc.stat().st_size / (1024 * 1024)
    try:
        with open(tmp_doc, "rb") as f:
            res = tg_call(bot_token, "sendDocument", data={"chat_id": chat_id, "caption": f"📁 <b>HD DOCUMENT ({doc_mb:.1f} MB) | TITLE:</b>\n<code>{esc_title}</code>"[:1024], "parse_mode": "HTML"}, files={"document": (mp4_path.name, f, "application/octet-stream")}, timeout=360)
    finally:
        tmp_doc.unlink(missing_ok=True)
    if not res.get("ok"):
        raise RuntimeError(f"sendDocument failed: {res}")
    tg_call(bot_token, "sendMessage", data={"chat_id": chat_id, "text": f"📝 <b>DESCRIPTION &amp; HASHTAGS (Tap to copy):</b>\n<pre>{esc_desc}</pre>"[:4096], "parse_mode": "HTML", "disable_web_page_preview": "true"})

def main():
    if not ensure_requests():
        return
    READY_DIR.mkdir(parents=True, exist_ok=True)
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    bot_token = str(cfg.get("bot_token", "")).strip()
    chat_id   = str(cfg.get("chat_id", "")).strip()
    print("=" * 68)
    print("  MODE 1: 24/7 TELEGRAM BOT REMOTE & SHORTS DISPATCHER")
    print(f"  Watching: {READY_DIR}")
    print("=" * 68)
    if not bot_token or "PASTE_YOUR" in bot_token or not chat_id or "PASTE_YOUR" in chat_id:
        log(f"[SETUP NEEDED] Edit {CONFIG_FILE} with your bot_token and chat_id, then restart.")
        return
    threading.Thread(target=telegram_listener_loop, args=(bot_token, chat_id), daemon=True).start()
    while True:
        if PAUSE_FLAG.exists():
            time.sleep(5)
            continue
        mp4_files = [p for p in sorted(READY_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime) if not p.name.endswith("_tgdoc.mp4")]
        if not mp4_files:
            time.sleep(10)
            continue
        mp4_path = mp4_files[0]
        if time.time() - mp4_path.stat().st_mtime < 5:
            time.sleep(3)
            continue
        txt_path = mp4_path.with_suffix(".txt")
        meta = parse_sidecar_txt(txt_path, mp4_path.stem)
        try:
            send_clip_to_telegram(bot_token, chat_id, mp4_path, meta)
            log(f"SENT! {mp4_path.name}")
            shutil.move(str(mp4_path), str(SENT_DIR / mp4_path.name))
            if txt_path.exists():
                shutil.move(str(txt_path), str(SENT_DIR / txt_path.name))
            time.sleep(SEND_DELAY_SECONDS)
        except Exception as e:
            log(f"[SEND ERROR] {mp4_path.name}: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()