# 🎬 24/7 Automated Stream Clipper & Telegram Mobile Remote

An end-to-end, hands-free Windows automation pipeline that monitors YouTube livestreams and channels 24/7, transcribes audio locally with Whisper, detects viral moments using audio spikes and live chat velocity, renders 9:16 split-screen vertical Shorts/Reels, and dispatches every clip directly to your phone via Telegram—complete with full remote control from your mobile chat.

---

## ✨ Key Features

- **100% Mobile-Controlled via Telegram:** Start, pause, stop, check live disk/queue status, or paste any YouTube stream link directly from your phone to add it to the clipping queue.
- **Score-Driven Viral Filtering (`Score > 70`):** Automatically discards low-energy filler and extracts only high-engagement moments scoring above 70/100 (capped at the top 20 non-overlapping scenes per stream).
- **Dynamic 30s–90s Clip Duration:** Adjusts clip length automatically between 30 and 90 seconds based on scene buildup, audio dB spikes, and chat surge multipliers.
- **9:16 Split-Screen Vertical Layout:** Places the streamer's facecam in the top half and gameplay in the bottom half with word-by-word English/Hinglish (`--language en`) captions and a hook title bar.
- **Smart Telegram Delivery (`sendVideo` + `sendDocument`):**
  - Clips under **50 MB** send as instant playable Telegram videos with tap-to-copy titles, descriptions, and hashtags.
  - High-bitrate 60–90s clips over **50 MB** automatically send as full-resolution Telegram Document files (with an automatic 47 MB transcode fallback if Telegram's Bot API upload ceiling is reached).
- **Zero Paid APIs Required:** Uses local `yt-dlp`, `whisper`, `OpenCV`, `Pillow`, and `FFmpeg`.

---

## 🏗️ System Architecture

```text
┌───────────────────────────┐        ┌──────────────────────────────────────┐
│   Your Phone (Telegram)   │◄──────►│         telegram_sender.py           │
│ • Start / Pause / Stop    │        │ • Listens for inline buttons & URLs  │
│ • Paste YouTube URLs      │        │ • Watches READY_TO_POST\             │
│ • Receive HD MP4 + Copy   │        │ • Sends Video/Document + Metadata    │
└───────────────────────────┘        └──────────────────┬───────────────────┘
                                                        │ Controls via PAUSE.flag
                                                        │ & Process Management
┌───────────────────────────┐        ┌──────────────────▼───────────────────┐
│   YouTube Channels &      │───────►│         auto_clip_factory.py         │
│   watchlist.txt Streams   │        │ • Full-stream audio + Whisper scan   │
└───────────────────────────┘        │ • Scores moments (>70) & cuts 30-90s │
                                     │ • Stages .mp4 + .txt to READY_TO_POST│
                                     └──────────────────────────────────────┘
```

---

## 📂 Repository Structure

```text
Telegram-Stream-Clipper/
├── engine/
│   └── scripts/
│       ├── streamclips.py           # Core Whisper, audio/chat analyzer & 9:16 renderer
│       ├── setup_env.py             # Private virtual environment & model installer
│       └── sc/                      # Frame detection, subtitles, titlebar & pipeline modules
├── auto_clip_factory.py             # 24/7 stream discovery, >70 scoring & 30-90s queue manager
├── telegram_sender.py               # Telegram remote control listener & HD clip dispatcher
├── Start_Telegram_Sender.bat        # One-click launcher for the Telegram controller
├── Pause_Play.bat                   # Local toggle to pause/resume or launch the clip factory
├── watchlist.txt                    # Target YouTube @handles and direct stream URLs
├── telegram_config.example.json     # Template for Telegram Bot token & Chat ID
├── .gitignore                       # Excludes secrets, logs, and rendered video folders
└── README.md
```

---

## 📋 Prerequisites (Windows 10 / 11)

1. **Python 3.12** installed (ensure `python` or `py -3.12` is available in PATH).
2. **FFmpeg** installed and accessible in system PATH:
   ```powershell
   winget install Gyan.FFmpeg
   ```
3. **Deno** (required by `yt-dlp` for YouTube signature extraction):
   ```powershell
   winget install DenoLand.Deno
   ```

---

## 🚀 End-to-End Setup Guide

### Step 1: Clone the Repository
```powershell
git clone [https://github.com/Its-Endless/Telegram-Stream-Clipper.git](https://github.com/Its-Endless/Telegram-Stream-Clipper.git) "D:\Automation Youtube Clipping"
cd "D:\Automation Youtube Clipping"
```

### Step 2: Create Your Telegram Bot & Get Your Chat ID
1. Open Telegram and message **[@BotFather](https://t.me/BotFather)**:
   - Send `/newbot`, choose a display name and username, and copy your **HTTP API Bot Token**.
2. Open your new bot in Telegram and tap **Start** (or send `/start`) so the bot can message you.
3. Message **[@userinfobot](https://t.me/userinfobot)** on Telegram and copy your numeric **Id** (for example, `123456789`).

### Step 3: Configure `telegram_config.json`
1. Copy the template file:
   ```powershell
   Copy-Item telegram_config.example.json telegram_config.json
   ```
2. Open `telegram_config.json` and enter your credentials:
   ```json
   {
     "bot_token": "YOUR_BOTFATHER_TOKEN",
     "chat_id": "YOUR_NUMERIC_CHAT_ID"
   }
   ```

### Step 4: Configure Your Stream Watchlist (`watchlist.txt`)
Edit `watchlist.txt` to list creator handles or direct stream URLs (one per line):
```text
youtube:@Mythpat
youtube:@LiveInsaan
youtube:@TechnoGamerzOfficial
youtube:@IShowSpeed
# Direct livestream or VOD URLs:
# [https://www.youtube.com/live/VIDEO_ID](https://www.youtube.com/live/VIDEO_ID)
```

### Step 5: Initialize the Clipping Engine (First-Time Only)
Run the setup command once to build the private `.streamclips` environment and download Whisper and face-detection models:
```powershell
python engine\scripts\streamclips.py setup
```

*(Note: If you clone into a folder other than `D:\Automation Youtube Clipping`, update `D_ROOT` and `PYTHON_EXE` at the top of `auto_clip_factory.py`, `telegram_sender.py`, `Start_Telegram_Sender.bat`, and `Pause_Play.bat`.)*

---

## 📱 Daily 24/7 Usage (Leave Laptop & Control from Mobile)

1. **Prevent Windows Sleep:** Go to **Windows Settings → System → Power & battery → Screen and sleep** and set **When plugged in, put my device to sleep after** to **Never**. Keep your laptop plugged into power.
2. **Start the Telegram Remote:** Double-click **`Start_Telegram_Sender.bat`** on your laptop.
   - Your phone will immediately receive **`🚀 Phone Remote Connected!`** with four interactive control buttons.
3. **Operate Entirely From Your Phone:**
   - **▶️ Start / Resume:** Launches `auto_clip_factory.py` on your laptop to begin scanning and clipping.
   - **⏸️ Pause All:** Pauses both clipping and Telegram dispatching without closing windows.
   - **⏹️ Stop Factory:** Stops the clipping process immediately.
   - **📊 Live Status:** Displays current state, queued clips count, total sent count, and free disk space.
   - **Paste Any YouTube Link:** Send any YouTube live/VOD URL in chat to immediately append it to `watchlist.txt` for priority clipping.

---

## ⚙️ Customization

| File | What You Can Customize |
| :--- | :--- |
| `auto_clip_factory.py` | Edit `SEARCH_ROTATION` (games/topics), `TEXT_MODE` (`"RELATABLE"` or `"NONE"`), minimum score (`> 70`), or clip duration (`30`–`90`s). |
| `watchlist.txt` | Add or remove `@handles` and direct stream URLs anytime (reloaded automatically every cycle). |
| `%USERPROFILE%\StreamClips\settings.json` | Customize caption colors (`cap_active`, `cap_color`), font size (`cap_size`), facecam split ratio (`cam_share`), and `min_score`. |
| `Pause_Play.bat` | Double-click locally on your laptop anytime to toggle pause/resume when at the keyboard. |

---

## 🛠️ Troubleshooting

- **Clips stay in `READY_TO_POST\` and don't send:** Check if `PAUSE.flag` exists in the root folder or tap **▶️ Start / Resume** in Telegram.
- **YouTube age-restricted or bot-check errors:** Sign into YouTube in Chrome on the same Windows profile; `auto_clip_factory.py` automatically retries with `--cookies chrome`.
- **Telegram `413 Request Entity Too Large`:** Handled automatically—`telegram_sender.py` switches to `sendDocument` and re-encodes oversized files to ~47 MB if needed.