# AICAM demo videos — generation prompts (v2: plain local kitchen, silent)

Put the finished videos in THIS folder (`backend\data\demo\`) with exactly these file names:

| File name | Scene | What it demonstrates |
|---|---|---|
| `01_compliant_chef.mp4` | Cook in full PPE | Green "OK" box, no alerts |
| `02_no_ppe_cook.mp4` | Cook with no PPE | No mask / No gloves / No hair cap alerts |
| `03_mixed_team.mp4` | Two cooks, one compliant, one not | Per-person boxes: one green, one red |
| `04_handwash_short.mp4` | 5-second hand wash, then prep | "Hand wash too short" alert |
| `05_handwash_skipped.mp4` | Walks straight to prep, no sink | "Hand wash skipped" alert |
| `06_dirty_table.mp4` | Empty table with leftover dishes | "Table not cleared" alert |

## Settings for every video
- Aspect ratio **16:9**, 720p or 1080p. Length: as long as the tool allows (8–20 s); the app loops it.
- **Camera motion: Static / None.** One continuous shot.
- **Audio: OFF.** If the tool has an audio / sound / music switch (e.g. Veo 3, Sora), turn it off.
  If it cannot be turned off, that is fine — the app ignores audio completely.
- **Style: none / realistic / "raw footage".** Do NOT pick "cinematic", "film", "epic" presets.
- Paste the NEGATIVE PROMPT below into the negative-prompt box if the tool has one.
  If it has no such box, the prompts already say "no music, no sound, not cinematic".

## NEGATIVE PROMPT
```
cinematic, movie scene, film look, dramatic lighting, epic, sci-fi, science fiction, futuristic, spaceship, space station, aerospace, laboratory, high-tech, neon, glowing lights, fantasy, dreamlike, luxury, five-star hotel, western fine dining, music, soundtrack, sound effects, voiceover, narration, camera movement, panning, zooming, drone shot, handheld shake, cuts, scene changes, slow motion, motion blur, steam clouds, smoke, fog, lens flare, depth of field blur, text, captions, subtitles, watermark, logo, distorted hands, extra fingers, fused fingers, morphing objects, gloves changing colour, distorted faces, people facing away, top-down view, fisheye, cartoon, anime, illustration, 3D render
```

---

## 01 — Compliant cook (`01_compliant_chef.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a small, typical local Indian restaurant kitchen: white tiled walls, a steel gas stove with burners on the back wall, large steel cooking vessels and a kadai, steel plates and bowls on open shelves, a plain steel work table in front. The camera is fixed high in the corner of the ceiling, looking down at about 35 degrees; the camera never moves. Normal white tube-light lighting. One Indian male cook stands behind the steel work table in the middle of the picture, facing the camera, seen from head to knees. He wears a white cook cap that covers all his hair, a light-blue disposable face mask over his nose and mouth, blue plastic gloves on both hands and a white apron over his shirt. He slowly chops onions on a wooden chopping board with a knife and puts the pieces into a steel bowl. Both of his hands are always visible above the table. One continuous shot, natural everyday movements.
```

## 02 — Cook without PPE (`02_no_ppe_cook.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a small, typical local Indian restaurant kitchen: white tiled walls, a steel gas stove with burners on the back wall, large steel cooking vessels, steel plates on open shelves, a plain steel work table in front. The camera is fixed high in the corner of the ceiling, looking down at about 35 degrees; the camera never moves. Normal white tube-light lighting. One young Indian male cook stands behind the steel work table in the middle of the picture, facing the camera, seen from head to knees. He has short black hair with NO cap, NO face mask so his nose and mouth are clearly visible, NO gloves so his bare hands are clearly visible, and he wears a plain grey t-shirt with NO apron. With his bare hands he picks up raw chicken pieces from a steel tray and cuts them on a wooden chopping board. Both hands always visible above the table. One continuous shot, natural everyday movements.
```

## 03 — Mixed team (`03_mixed_team.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a small, typical local Indian restaurant kitchen: white tiled walls, a steel gas stove on the back wall, steel vessels and plates on shelves, a long plain steel work table in front. The camera is fixed high in the corner of the ceiling, looking down at about 35 degrees; the camera never moves. Normal white tube-light lighting. Two Indian male cooks stand side by side behind the long steel table, about one metre apart, both facing the camera, both seen from head to knees. The cook on the LEFT wears a white cook cap covering all his hair, a light-blue face mask over nose and mouth, blue plastic gloves on both hands and a white apron. The cook on the RIGHT has uncovered black hair, no face mask with nose and mouth visible, bare hands with no gloves, a black t-shirt and no apron. Both slowly cut tomatoes on wooden chopping boards, hands always visible above the table. One continuous shot, natural everyday movements.
```

## 04 — Hand wash too short (`04_handwash_short.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a small, typical local Indian restaurant kitchen seen from a wide angle: white tiled walls, normal white tube-light lighting. On the LEFT side of the picture is a small steel hand-wash basin with a tap and a soap bottle on the wall. On the RIGHT side of the picture is a plain steel work table with a wooden chopping board and vegetables. Open floor in the middle. The camera is fixed high in the corner of the ceiling, looking down at about 35 degrees; the camera never moves. One Indian male cook wearing a white cook cap, a light-blue face mask and a white apron, whole body visible from head to feet, walks from the middle to the LEFT basin, quickly rinses his hands under the tap for only about five seconds without using soap, shakes the water off, then walks straight to the RIGHT work table and starts chopping vegetables, facing the camera. One continuous shot, normal walking speed.
```

## 05 — Hand wash skipped (`05_handwash_skipped.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a small, typical local Indian restaurant kitchen seen from a wide angle: white tiled walls, normal white tube-light lighting. On the LEFT side of the picture is a small steel hand-wash basin with a tap and a soap bottle on the wall. On the RIGHT side of the picture is a plain steel work table with raw chicken on a chopping board. Open floor in the middle. The camera is fixed high in the corner of the ceiling, looking down at about 35 degrees; the camera never moves. One Indian male cook wearing a white cook cap, a light-blue face mask and a white apron, whole body visible from head to feet, walks in from the middle of the picture, does NOT go to the basin at all, walks straight to the RIGHT work table and starts handling the raw chicken with his hands for the rest of the video, facing the camera. One continuous shot, normal walking speed.
```

## 06 — Dirty table (`06_dirty_table.mp4`)
```
Silent, ordinary CCTV surveillance camera recording, not cinematic, plain everyday footage with no music and no sound. Inside a simple, typical local Indian family restaurant dining hall: plain painted walls, ceiling fans, normal white tube-light lighting, simple tables and plastic or wooden chairs. The camera is fixed high in the corner of the ceiling, looking down at about 40 degrees; the camera never moves. In the middle of the picture is one empty four-seat table with its chairs; nobody is sitting at it and nobody walks near it. On the table are clearly visible leftovers from a finished meal: two used steel plates, two steel bowls, two steel tumblers, a plastic water bottle, spoons, and crumpled tissue paper. The rest of the hall is quiet and empty. Only a ceiling fan turning slowly. One continuous shot.
```

---

## If the result still looks cinematic
- Put the words **"CCTV", "surveillance", "security camera"** at the very start (already done) and choose the tool's "realistic / raw" style.
- Remove any remaining quality words the tool adds automatically ("4K", "HDR", "cinematic").
- Try the **image-to-video** mode: first generate (or photograph) a still image of a local kitchen from a CCTV angle, then animate it with the prompt. This keeps the setting exactly right.
- Real footage works even better: a short phone video of a real kitchen, held still on a shelf high up, is the best test of all.
