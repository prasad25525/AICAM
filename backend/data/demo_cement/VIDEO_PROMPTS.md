# VigilSiddhi — Cement plant demo videos (Phase 1) — generation prompts

Put the finished videos in THIS folder (`backend\data\demo_cement\`) with exactly these file names:

| File name | Scene | What it demonstrates |
|---|---|---|
| `01_ppe_compliant.mp4` | Worker in helmet + hi-vis vest | Green "OK" box, no alerts |
| `02_no_ppe_worker.mp4` | Worker without helmet and vest | "No helmet" + "No vest" alerts |
| `03_mixed_crew.mp4` | Two workers: one compliant, one not | Per-person boxes: one green, one red |
| `04_restricted_area.mp4` | Worker steps into a marked danger zone | "Restricted area entry" alert |
| `05_conveyor_spillage.mp4` | Material spilling off a conveyor belt | "Conveyor spillage" alert |
| `06_conveyor_normal.mp4` | Same conveyor running cleanly | No alert (proves no false alarms) |
| `07_bag_counting.mp4` | Cement bags moving one by one on a loader belt | Live bag count |

## Settings for every video
- Aspect ratio **16:9**, 720p or 1080p. Length: as long as the tool allows (8–20 s); the app loops it.
- **Camera motion: Static / None.** One continuous shot, no cuts.
- **Audio: OFF.** If the tool has an audio / sound / music switch, turn it off. (If it can't, that's fine — the app ignores audio.)
- **Style: none / realistic / "raw footage".** Do NOT pick "cinematic", "film", "epic" presets.
- Paste the NEGATIVE PROMPT below into the negative-prompt box if the tool has one.
- People must be **clearly visible, head to feet, facing the camera, not tiny in the distance** — the AI needs to see the head and chest to judge helmet and vest.

## NEGATIVE PROMPT
```
cinematic, movie scene, film look, dramatic lighting, epic, sci-fi, futuristic, neon, glowing lights, fantasy, music, soundtrack, sound effects, voiceover, narration, camera movement, panning, zooming, drone shot, handheld shake, cuts, scene changes, slow motion, motion blur, thick dust cloud, smoke, fog, haze, fire, flames, sparks, welding, explosion, accident, injury, lens flare, depth of field blur, text, captions, subtitles, watermark, logo, brand name, readable signs, distorted hands, extra fingers, distorted faces, people facing away, helmets appearing or disappearing, vest changing colour, morphing objects, tiny distant people, top-down view, fisheye, cartoon, anime, illustration, 3D render
```

---

## 01 — Compliant worker (`01_ppe_compliant.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant production area in daylight: a large open steel shed with a grey concrete floor lightly covered in cement dust, steel columns, yellow-painted handrails, large grey machinery and steel pipes in the background. The camera is fixed high on a steel column, looking down at about 30 degrees; the camera never moves. One Indian male worker stands in the middle of the picture, facing the camera, seen clearly from head to feet, taking up about half the height of the picture. He wears a white hard-hat safety helmet, a bright orange high-visibility safety vest with silver reflective stripes over a blue work shirt, dark trousers and black safety shoes. He slowly checks a clipboard, looks up at the machine, and takes a few small steps, always facing the camera. One continuous shot, natural everyday movements.
```

## 02 — Worker without helmet and vest (`02_no_ppe_worker.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant production area in daylight: a large open steel shed with a grey concrete floor lightly covered in cement dust, steel columns, yellow-painted handrails, large grey machinery and steel pipes in the background. The camera is fixed high on a steel column, looking down at about 30 degrees; the camera never moves. One young Indian male worker stands in the middle of the picture, facing the camera, seen clearly from head to feet, taking up about half the height of the picture. He has short black hair with NO helmet, so his bare head and hair are clearly visible, and he wears a plain light-blue shirt with NO safety vest, dark trousers and sandals. He slowly checks a clipboard, looks up at the machine, and takes a few small steps, always facing the camera. One continuous shot, natural everyday movements.
```

## 03 — Mixed crew (`03_mixed_crew.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant production area in daylight: a large open steel shed with a grey concrete floor lightly covered in cement dust, steel columns, yellow-painted handrails, large grey machinery in the background. The camera is fixed high on a steel column, looking down at about 30 degrees; the camera never moves. Two Indian male workers stand side by side about two metres apart in the middle of the picture, both facing the camera, both seen clearly from head to feet. The worker on the LEFT wears a yellow hard-hat safety helmet and a bright orange high-visibility vest with silver reflective stripes over a grey shirt. The worker on the RIGHT has uncovered black hair with NO helmet and wears a plain dark-blue shirt with NO safety vest. They talk to each other and point at the machinery, always facing the camera. One continuous shot, natural everyday movements.
```

## 04 — Restricted area entry (`04_restricted_area.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant in daylight, seen from a wide angle: a grey concrete floor lightly covered in cement dust. On the RIGHT half of the picture is a large grey crusher machine; the floor around it is marked off as a danger area by a wide yellow-and-black striped line painted on the floor, with a short yellow metal barrier. The LEFT half of the picture is an open walkway. The camera is fixed high on a steel column, looking down at about 35 degrees; the camera never moves. One Indian male worker wearing a white safety helmet and an orange high-visibility vest, whole body visible from head to feet, walks along the LEFT walkway, then steps over the yellow-and-black line into the marked danger area right next to the crusher, stands there for about five seconds looking at the machine, then walks back out to the walkway. One continuous shot, normal walking speed.
```

## 05 — Conveyor spillage (`05_conveyor_spillage.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant in daylight: a long black rubber conveyor belt runs from left to right across the middle of the picture on a grey steel frame, about one metre above a grey concrete floor, carrying grey crushed limestone and clinker. The camera is fixed high on a steel column, looking down at about 35 degrees at the side of the conveyor; the camera never moves. The belt is overloaded and grey material keeps spilling over the edge of the belt and falling onto the floor below it, forming a clearly visible growing pile of grey material on the floor under the conveyor. No people in the picture. One continuous shot, the belt moving at a steady speed.
```

## 06 — Conveyor running normally (`06_conveyor_normal.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant in daylight: a long black rubber conveyor belt runs from left to right across the middle of the picture on a grey steel frame, about one metre above a clean grey concrete floor, carrying an even, moderate layer of grey crushed limestone. The camera is fixed high on a steel column, looking down at about 35 degrees at the side of the conveyor; the camera never moves. The material stays in the middle of the belt and nothing falls off; the floor under the conveyor stays clean and empty. No people in the picture. One continuous shot, the belt moving at a steady speed.
```

## 07 — Cement bag counting (`07_bag_counting.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a typical Indian cement plant packing and dispatch area in daylight: a short inclined steel belt conveyor runs from the left side of the picture to the right side, where the back of a parked truck is being loaded. The camera is fixed high on a steel column, looking from the side at about 30 degrees down; the camera never moves. Full 50 kg cement bags — plain white woven bags with no readable text or logo — move along the belt one at a time from left to right, evenly spaced about one metre apart, so every bag is clearly separate from the next. On the right, one worker in a white helmet and orange vest lifts each bag off the end of the belt and stacks it in the truck. One continuous shot, the belt moving at a steady speed.
```

---

## If the result is not right
- **Looks cinematic:** keep "CCTV", "surveillance" at the very start and choose the tool's realistic / raw style; remove quality words it adds automatically ("4K", "HDR", "cinematic").
- **Helmet or vest keeps appearing/disappearing:** regenerate, or use **image-to-video**: first generate a still image of the scene, check the worker is dressed correctly, then animate it with the same prompt.
- **People too small:** add "close to the camera, filling half the picture height".
- **Bags stuck together (07):** add "large gaps between bags, one bag at a time".
- Real footage from a plant beats all of these — a short phone video held still from a high point is the best test.
