# VigilSiddhi — Cement plant demo videos (Phase 2) — generation prompts

Put the finished videos in THIS folder (`backend\data\demo_cement\`) with exactly these file names
(remove any double `.mp4.mp4` the download adds):

| File name | Scene | What it demonstrates |
|---|---|---|
| `08_damaged_bag.mp4` | Bags on the loader belt, one torn and leaking powder | "Damaged cement bag" alert |
| `09_truck_entry.mp4` | A truck drives in through the plant gate | Truck logged **IN** |
| `10_truck_exit.mp4` | A loaded truck drives out through the same gate | Truck logged **OUT** |
| `11_dust_emission.mp4` | Grey dust cloud rising from a conveyor transfer point | "Visible dust" alert |
| `12_dust_clear.mp4` | The same spot, clear air | No alert (proves no false alarms) |

(`07_bag_counting.mp4` from Phase 1 already shows intact bags, so it is the "no damage" check for 08.)

## Settings for every video
- Aspect ratio **16:9**, 720p or 1080p. Length: as long as the tool allows (8–20 s); the app loops it.
- **Camera motion: Static / None.** One continuous shot, no cuts.
- **Audio: OFF.**
- **Style: none / realistic / "raw footage".** Not "cinematic".
- Paste the NEGATIVE PROMPT below — **except for video 11**, which uses its own (it needs the dust).

## NEGATIVE PROMPT (videos 08, 09, 10, 12)
```
cinematic, movie scene, film look, dramatic lighting, epic, sci-fi, futuristic, neon, fantasy, music, soundtrack, sound effects, voiceover, narration, camera movement, panning, zooming, drone shot, handheld shake, cuts, scene changes, slow motion, motion blur, smoke, fog, haze, fire, flames, sparks, explosion, accident, injury, lens flare, depth of field blur, text, captions, subtitles, watermark, logo, brand name, readable signs, readable number plates, distorted vehicles, morphing objects, objects appearing or disappearing, top-down view, fisheye, cartoon, anime, illustration, 3D render
```

## NEGATIVE PROMPT (video 11 only)
```
cinematic, movie scene, film look, dramatic lighting, epic, sci-fi, futuristic, neon, fantasy, music, soundtrack, sound effects, voiceover, narration, camera movement, panning, zooming, drone shot, handheld shake, cuts, scene changes, slow motion, fire, flames, sparks, explosion, black smoke, steam, accident, injury, lens flare, text, captions, subtitles, watermark, logo, brand name, morphing objects, top-down view, fisheye, cartoon, anime, illustration, 3D render
```

---

## 08 — Damaged bag (`08_damaged_bag.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant packing area in daylight: a short steel belt conveyor runs from the left side of the picture to the right side across the middle of the picture. The camera is fixed high on a steel column, looking from the side at about 30 degrees down at the belt, fairly close so the bags look large; the camera never moves. Full 50 kg cement bags — plain white woven bags with no readable text or logo — move along the belt one at a time from left to right, with clear gaps between them. One bag in the middle of the line is badly torn open along its side: a large rip, with grey cement powder pouring out of the tear and spreading in a small grey heap on the black belt around it and leaving a grey trail behind it. All the other bags are intact and clean. No people in the picture. One continuous shot, the belt moving slowly at a steady speed.
```

## 09 — Truck entry (`09_truck_entry.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. The main vehicle gate of a typical Indian cement plant in daylight: a wide open sliding steel gate, a small security cabin on one side, a concrete road leading into a dusty plant yard with grey silos in the background. The camera is fixed high on a pole beside the gate, looking down at about 35 degrees across the road, so vehicles pass from the LEFT side of the picture to the RIGHT side; the camera never moves. One empty Indian heavy goods truck (a plain orange or yellow lorry with an open cargo body, no readable text, no readable number plate) drives slowly in from the LEFT edge of the picture, through the open gate, and continues out of the RIGHT edge of the picture into the plant. The whole truck is clearly visible while it passes. No other vehicles. One continuous shot, steady slow driving speed.
```

## 10 — Truck exit (`10_truck_exit.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. The main vehicle gate of a typical Indian cement plant in daylight: a wide open sliding steel gate, a small security cabin on one side, a concrete road leading out of a dusty plant yard with grey silos in the background. The camera is fixed high on a pole beside the gate, looking down at about 35 degrees across the road; the camera never moves. One Indian heavy goods truck (a plain orange or yellow lorry, no readable text, no readable number plate) loaded with stacked white cement bags covered by a tarpaulin drives slowly in from the RIGHT edge of the picture, through the open gate, and continues out of the LEFT edge of the picture, leaving the plant. The whole truck is clearly visible while it passes. No other vehicles. One continuous shot, steady slow driving speed.
```

## 11 — Visible dust (`11_dust_emission.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant in daylight: a conveyor transfer point where one conveyor belt drops crushed grey material onto another, under a steel chute, with steel structures and grey silos in the background. The camera is fixed high on a steel column, looking at the transfer point from about 10 metres away at 30 degrees down; the camera never moves. A thick cloud of light grey cement dust is continuously billowing out of the chute and the transfer point, rising and drifting to the side and clearly hazing the steel structures behind it, so the area around the transfer point looks visibly dusty and blurred by grey dust. No people in the picture. One continuous shot, the dust moving naturally.
```

## 12 — Clear air (`12_dust_clear.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant in daylight: a conveyor transfer point where one conveyor belt drops crushed grey material onto another, under a steel chute, with steel structures and grey silos in the background. The camera is fixed high on a steel column, looking at the transfer point from about 10 metres away at 30 degrees down; the camera never moves. The air is completely clear: no dust cloud at all, the steel structures and silos behind are sharp and clearly visible, and the material moves cleanly from one belt to the other. No people in the picture. One continuous shot, the belts moving at a steady speed.
```

---

## If the result is not right
- **08 — the tear isn't obvious:** add "a large clearly visible rip, a lot of grey powder pouring out". Generate a still image first and animate it if the tool keeps hiding the damage.
- **09 / 10 — truck changes shape or appears from nowhere:** regenerate, or shorten to "drives slowly across the picture from left to right". The truck must **enter from one side and leave from the other** — that's what the counter needs.
- **11 — looks like fire smoke:** say "light grey powdery cement dust" and keep "black smoke, fire" in the negative prompt.
- **11 and 12 must show the same spot** from the same angle: generate 12 first, then use its first frame as the start image for 11 (image-to-video) if your tool allows.
- Real footage beats all of these — even a short phone video from the plant gate or packing line.
