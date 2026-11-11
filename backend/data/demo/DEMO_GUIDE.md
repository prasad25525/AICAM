# AICAM — demo guide

## Before the audience arrives (5 minutes)
1. Start the backend: `cd F:\Azkashine\AICAM\backend` → `.\.venv\Scripts\python.exe main.py`
2. Start the frontend: `cd F:\Azkashine\AICAM\frontend` → `npm run dev`
3. Check **Settings** (sidebar): **Record events** and **Pop-up alerts** must be ON, or no alerts appear.
4. Set up the demo with a clean slate:
   `.\.venv\Scripts\python.exe scripts\setup_demo.py --clear-events` (from the backend folder)
5. Open http://127.0.0.1:5173, pick the **Restaurant** tab, and log in. Wait ~30 s on **Live View** until every tile shows boxes
   (the AI models load the first time).
6. Close other heavy apps (browser tabs, Teams/Zoom): the laptop CPU is the bottleneck, not the GPU.

## Suggested running order (about 10 minutes)
| # | Page | What to show | What to say |
|---|---|---|---|
| 1 | **Live View** | 6 cameras, boxes on every person | "Every camera is analysed by AI. Green = compliant, red = something missing, with the reason." |
| 2 | Live View → **Camera to show** dropdown → Demo 3 | Big single view with **Fast detection** (AI ~2–3/s): left cook green OK, right cook red: No hair cap / No mask / No gloves | "It judges each person separately — one camera, two different answers." |
| 3 | Dropdown → Demo 1 | Green OK, no alerts | "No false alarms when staff follow the rules." |
| 4 | Pop-up alerts (top right) | A critical alert with snapshot, sound | "Supervisors are alerted within seconds, with evidence." |
| 5 | **Events & Alerts** | Open an event: annotated snapshot, "Rule broken" card (missing item, or e.g. washed 4s / 20s required bar); Acknowledge → Resolve with a note | "Every violation shows exactly what was wrong, with a photo and an audit trail." |
| 6 | Events: "Handwash too short @ Hand sink" and "Handwash skipped @ Prep table" | Zone-based rules | "It follows people between the sink and the prep table — not just what they wear." |
| 7 | Live View → tick **Show zones** on Demo 4/5 | The sink and prep zones | "Zones are drawn once per camera, on the Zones page." |
| 8 | Events: "Table not cleared @ Table 1" | Dining-area rule | "Front-of-house too: tables left with dishes." |
| 9 | **Dashboard** | Hygiene score, violations by hour/type, camera status | "The manager's one-page view." |
| 10 | **Reports** → Export CSV | Trends, busiest hours, by camera/zone; CSV opens in Excel | "For audits and for comparing branches." |

## Accuracy on these demo videos (from `scripts\analyze_videos.py`)
| Item | Accuracy | Model gave an answer |
|---|---|---|
| Hair cap / hairnet | 100% | 98% of frames |
| Face mask | 99% | 98% |
| Gloves | 98% | 91% |
| Apron | 79% | 71% (white apron over white clothes is hard) |

(Measured on the 12 fps demo copies the app actually plays, 120 checks per item.)

Be clear with the audience: these are **clean AI-generated videos**. Real kitchens (steam, crowding,
bad angles) will score lower until the model is trained on footage from the actual kitchens.
The apron check is switched off on the hand-wash cameras for this reason.

## Handy commands (backend folder)
- `scripts\setup_demo.py --clear-events` — reset demo events and settings
- `scripts\setup_demo.py --off` — stop detection on the demo cameras (frees the laptop)
- `scripts\setup_demo.py --remove` — delete the demo cameras
- `scripts\setup_demo.py --full` — use the original 720p videos (needs a stronger CPU)
- `scripts\analyze_videos.py` — re-run the accuracy check (needs `ground_truth.json`)

## Performance on this laptop (GTX 1650)
- **All cameras (grid):** each camera is checked about every 2–3 s; alerts appear 5–10 s after a violation starts.
- **One camera (dropdown, Fast detection on):** only that camera is analysed — about 2–3 checks per second
  (≈4–5× faster), boxes follow people closely. The other cameras are paused and raise no alerts until you
  return to "All cameras" (or close the page — focus ends by itself within 30 s).
- The demo uses 12 fps copies of the videos at full 1280×720 (`data\demo\lite\`). Smaller copies were tried
  and lowered glove accuracy (640×360: 87%, 960×540: 94%, 1280×720: 98%).
