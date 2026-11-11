# VigilSiddhi — Cement plant demo guide

## Set up (once, or to refresh)
From the backend folder, with the backend running:
```
.\.venv\Scripts\python.exe scripts\setup_demo.py --industry cement --clear-events
```
This switches the app to **Cement plant**, adds the 7 demo videos as cameras, draws the crusher danger
zone on camera 4, the floor-under-conveyor zone on cameras 5 and 6 and the loader-belt counting zone on camera 7,
and switches detection on for all 7.
Then open http://127.0.0.1:5173, pick the **Cement plant** tab, and log in.
Check **Settings → Record events** and **Pop-up alerts** are ON, or no alerts appear.

## What each camera shows
| Camera | What to show | Detection |
|---|---|---|
| Cement 1 · PPE compliant | Green "OK": helmet and vest worn | ✅ helmet + vest |
| Cement 2 · No helmet or vest | Red "No helmet / No vest", critical alert | ✅ helmet + vest |
| Cement 3 · Mixed crew | One green, one red — judged per person | ✅ helmet + vest |
| Cement 4 · Restricted area | Red "IN DANGER ZONE" marker, critical alert with the zone and time inside | ✅ restricted area (+ PPE) |
| Cement 5 · Conveyor spillage | Red "CONVEYOR SPILLAGE" badge on the floor zone, warning alert | ✅ spillage |
| Cement 6 · Conveyor normal | Green "Floor under conveyor: clear" — never alerts | ✅ spillage |
| Cement 7 · Bag counting | Counting line on the belt, "BAGS 44 · 28/min"; Dashboard tile "Bags counted today" | ✅ bag counting |

Use the **Camera to show** dropdown with **Fast detection** for one camera at a time (about 3 AI checks per second).

## Accuracy on these videos (scripts\analyze_videos.py data\demo_cement)
| Item | Accuracy | Model gave an answer |
|---|---|---|
| Safety helmet | 99% | 88% of frames |
| Safety vest | 100% | 99% |

Danger zone (camera 4): the worker is inside for about 4.5 s of each 10 s loop; the live view measured 4.1 s.
Only the feet count — walking past the line does not.

Spillage (1 minute live): camera 5 "spillage" in 59 of 59 checks (P 0.98–1.00); camera 6 "clear" in 59 of 59
(P 0.00–0.01) — no false alarm.

Bag counting: 5 bags per 10 s loop (the bags the worker loads; about 9 different bags are seen, the rest
are still on the belt when the clip loops). Live for 1 minute with all 7 cameras running: 29 counted, 30 expected.
Counting needs the gap or seam between bags to show: bags pressed tightly end to end may be counted as one.

Be clear with the audience: these are **clean AI-generated videos**. Real plants (dust, glare, distant
workers) will score lower until the system is tuned on footage from the actual site.

## Switch back to the restaurant demo
Top bar → **Cement plant ▾ → Restaurant**, or log out and pick the Restaurant tab.
