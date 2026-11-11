# VigilSiddhi — A Vision AI Platform · Installation guide

Powered by Azkashine Software & Services Pvt. Ltd.

## 1. What the computer needs

| | Minimum | Recommended |
|---|---|---|
| Windows | Windows 10 or 11, 64-bit | Windows 11 |
| GPU | NVIDIA, 4 GB (e.g. GTX 1650) — works without one, but very slowly | RTX 3060 / 4060 or better |
| CPU / RAM | 4 cores / 8 threads, 16 GB RAM | 8+ cores, 32 GB RAM |
| Disk | 15 GB free (SSD) | 50 GB+ (event snapshots) |
| Internet | Needed once, for installing (about 6 GB of downloads: libraries + AI models) | — |

With an NVIDIA GPU, install the latest **NVIDIA driver** first (https://www.nvidia.com/drivers).

## 2. Install the two free tools (once)

1. **Python 3.11** — https://www.python.org/downloads/release/python-3119/ → "Windows installer (64-bit)".
   During setup tick **"Add python.exe to PATH"**. (Use 3.11 — newer versions are not supported.)
2. **Node.js LTS** — https://nodejs.org/ → the LTS installer, default options.

## 3. Install VigilSiddhi

1. Get the code: download it from GitHub (**Code → Download ZIP**, then unzip) or `git clone https://github.com/PrasadRaoJ/AICAM.git`,
   into a folder such as `D:\VigilSiddhi`.
2. Double-click **`install.bat`** and wait. The first time takes **15–40 minutes** (it downloads the AI libraries and models).
   It ends with "Installed". If it stops, read the message — it says what is missing.

## 4. Start it

Double-click **`start.bat`**. Two windows open (**VigilSiddhi backend** and **VigilSiddhi frontend**) and the
browser opens http://127.0.0.1:5173 after about 15 seconds.

- Pick the industry tab (**Restaurant** or **Cement plant**) and **Sign in** (admin / admin123).
- Keep the two windows open while using it. Close them to stop VigilSiddhi.
- The AI models load about 30 seconds after the first camera starts detecting.

## 5. Try the demo videos (optional)

The demo videos are **not** in the repository (they are large). Generate them with the prompts in
`backend\data\demo\VIDEO_PROMPTS.md` and `backend\data\demo_cement\VIDEO_PROMPTS*.md` (or copy them from
Azkashine), put them in those folders with the listed file names, then, with VigilSiddhi running, open a Command Prompt in the `backend` folder and run:

```
.venv\Scripts\python.exe scripts\setup_demo.py --industry cement --clear-events
.venv\Scripts\python.exe scripts\setup_demo.py --industry restaurant --clear-events
```

Each adds that industry's demo cameras with their zones and detection switched on. Then open **Live View**.
Guides: `backend\data\demo\DEMO_GUIDE.md` (restaurant) and `backend\data\demo_cement\DEMO_GUIDE.md` (cement).
In **Settings**, switch **Record events** and **Pop-up alerts** on to get alerts.

## 6. Before real use — change the password

1. Open `backend\.env` in Notepad and change `AICAM_ADMIN_PASSWORD=admin123` to your own password.
   (Also change it in `frontend\.env.development`, which only pre-fills the login form.)
2. For a customer site with one industry, uncomment `AICAM_INDUSTRY_LOCK=cement` (or `restaurant`):
   the login page then shows only that industry.
3. Close the two windows and run `start.bat` again.

## 7. Adding the site's cameras

**Cameras → Add camera → Stream URL**, paste the camera's RTSP link, press **Test connection**, then **Save**.
If it fails, the message says why (wrong password, wrong path, secure RTSP, not reachable…).
Set each camera to **1280×720 (or 1080p), 12–15 fps, H.264** in the camera's own settings — higher
resolutions overload the computer. Then draw zones on the **Zones** page and switch detection on in **Cameras**.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `install.bat`: "Python 3.11 was not found" | Install Python 3.11 with "Add to PATH" ticked; open a new window and run it again |
| `install.bat` stops while downloading | Check the internet connection and run `install.bat` again — it continues |
| Browser says "can't reach this page" | Wait 20 s and refresh; check both windows are still open and show no red errors |
| "Port 8000 / 5173 is already in use" | VigilSiddhi is already running (or another app uses the port): close the old windows first |
| AI is very slow, CPU near 100% | Lower the cameras to 720p / 12 fps; use fewer cameras with detection on; see the recommended hardware above |
| No boxes on Live View | Detection must be switched on for the camera (Cameras page); the models need ~30 s to load the first time |
| No alerts | Settings → **Record events** and **Pop-up alerts** must be on |

## What is in the repository

- `backend\` — the server and AI (Python), database migrations, scripts, demo guides and video prompts.
  The AI models are downloaded into `backend\models` by `install.bat` (`scripts\download_models.py`).
- `frontend\` — the web app (React).
- No cameras, events or passwords from other sites: the database is created fresh on first start.
