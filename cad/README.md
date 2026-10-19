# Easy Scanner — printable parts

The hardware of the scanner: a phone clamp and a ball-head mount for the
line laser. Both snap onto a 16 × 13 mm aluminium profile, which is the
scanner's frame. The models are Python on [CadQuery](https://cadquery.readthedocs.io/),
units are millimetres.

## Contents

| Path | What it is |
|---|---|
| `models/profile_clip.py` | The shared snap-on channel for the 16 × 13 profile: two toothed walls, slot and tooth parameters |
| `models/ball_mount.py` | Ball-head laser mount: snap-on block with a collet, ball, nut, L-shaped clamp for a Ø12 laser module |
| `models/laser_clamp_cross.py` | The first laser clamp (laser across the screw axis) — an alternative to the L-shaped clamp, bore 12.0 |
| `export/` | Our parts in print orientation (`export_stl.py`) |
| `phone-clamp/` | The phone clamp — a remix of a third-party model, **under its own licence** ([phone-clamp/README.md](phone-clamp/README.md)) |
| `export_stl.py` | Writes every printable part to `export/` and `phone-clamp/export/` |

Every part model exposes `PARAMS` (default, min, max, step per parameter) and
`build(params)` returning a CadQuery shape (`profile_clip.py` is a shared helper), so it opens in any CadQuery viewer
(CQ-editor, OCP CAD Viewer) or a small preview harness of your own.

## Export

```powershell
pip install cadquery numpy
cd cad
python export_stl.py
```

The phone clamp is built from meshes, so it is slow: the first sewing of the
STL takes up to 2.5 minutes, then the solid is cached as `.brep` next to the
STL (ignored by git) and reused until the STL changes.

## Profile snap-on channel

Slot 16.4 × 13.2 (the 16 × 13 profile plus 0.2). A 0.6 mm tooth at the foot of
each wall catches the profile's bottom face; the lead-in chamfer under the
tooth spreads the walls when the part is pushed onto the profile from above.
The profile can also be slid in from the end — the slot goes through. The
outer face of each wall is a convex arc from the part's edge down to the foot
of the wall: a thick root and no overhangs when printed walls-down. Peak
strain at the root when snapping on is ~1.6 %; a 0.7 mm tooth gives ~2 %,
already close to PLA's limit, especially since the wall bends across the
layers.

## Ball-head laser mount

Top to bottom:

- **Laser clamp**, L-shaped: the laser axis is parallel to the screw axis.
  A column on a Ø11 × 15 mm boss: a through hole for an M5 socket head cap
  screw, the head in a counterbore open at the top, seated on a 45° cone
  (prints without support). From the column a link with a common top runs to
  a vertical split ring for a Ø12 laser module, bored 11.8 so the plastic
  grips it. The axis distance is nut radius + laser radius + `laser_clear`
  (18 + 6 + 4 = 28 mm by default): in plan the laser body is 4 mm outside the
  nut and hangs past it; with the ball tilted up to 45° a laser up to 30 mm
  long below the ring does not touch the nut (the chamfered boss against the
  nut limits the tilt earlier, at 43–44°). The block sits 27.5 mm below the
  ring; its corner (half-diagonal 21.2 mm) is only 0.8 mm from the laser in
  plan, which matters only if the module sticks out below the ring further
  than that and the link is turned towards the block's corner.
  The link follows the outer tangents of the column (R 6.6) and ring (R 7.9)
  outlines, over the full ring height (16 mm) down to the boss; a 7 mm through
  slot runs from the end of the brace to the ring wall (2.8 mm of wall remains
  at the root); under the link a 45° brace rests on the boss (ending 3 mm
  above its bottom).
  The ring lips taper: the outer outline is offset towards the root, the wall
  thins from 2.8 mm at the root to 1.2 mm at the split, the split edges are
  rounded, the bore has 0.5 mm lead-in chamfers at both ends. The tangent
  link walls hold the lips almost to the middle of the ring (~90° from the
  root), so the ring is stiffer than with a narrow lever entering only at the
  root: a plane FEA estimate of the section (one-sided contact, 0.2 mm
  interference) gives ~210 N on the laser against ~100 N, peak strain ~0.37 %
  against ~0.28 %; the slot takes ~15 % of the force off, the wall thickness
  at its end hardly matters. The strains are far from PLA's limit.
  Printed upside down, flat top on the bed — both holes vertical, no support
  needed (about 44 min, 6.5 cm³).
- **First laser clamp** (`models/laser_clamp_cross.py`) — the alternative to
  the L-shaped clamp: the laser across the screw, a split ring above the
  Ø11 × 15 boss, the screw head goes down through the split into a
  counterbore under the channel (screw first, then the laser). A 11.8 bore
  held too tight, so `laser_grip` is 0 here — bore 12.0. Printed boss down,
  the top of the channel is a teardrop towards the split, no support needed
  (about 33 min, 3.7 cm³).
- **Ball Ø20** with a flat for the boss and a Ø4.2 hole to the centre (8.3 mm
  from the flat) — tap it M5. An M5 × 25 screw passes ~17 mm of the clamp and
  engages the ball by about 8 mm.
- **Nut** — internal P3 thread and an internal 11° cone. Tightening, the cone
  presses on the collet fingers: ~0.7 mm of free travel, over the full 2.5 mm
  travel the fingers squeeze the ball by 0.35 mm in radius.
- **Block 30 × 30** with the profile snap-on channel and the collet: a
  spherical seat, four fingers reaching 3 mm above the ball's equator
  (opening Ø19.4 for the Ø20 ball — the ball snaps in), a P3 Ø28 thread below,
  and a plain neck between the thread and the fingers for the nut's travel.

Print orientation: block walls down, ball flat down, nut thread down, clamp
flat top down. The slot ceilings (a 16.4 mm bridge at ~15 mm height) sagged,
so prints of the phone clamp base and the block use support under bridges too
(PrusaSlicer `dont_support_bridges = 0`). Reference print: PLA 230 °C, 0.15 mm
layers; the whole ball mount is 25.9 cm³, about 2 h 31 min.
Fits were checked by intersecting the solids (the assembly has clearances,
with the nut at 2.5 mm the interference is on the fingers only, the threads
do not touch).
