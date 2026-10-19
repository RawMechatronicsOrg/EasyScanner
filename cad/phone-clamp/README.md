# Phone clamp

The phone holder is [Tripod Mobile Phone Clamp V2](https://www.printables.com/model/25969-tripod-mobile-phone-clamp-v2)
by [Stamos](https://www.printables.com/@Stamos) (slim-phone variant), remixed
for the scanner. Licence: **CC BY-NC-SA 4.0** — see [LICENSE](LICENSE). It is
not covered by the CERN-OHL-S licence of the rest of `cad/`.

| Path | What it is |
|---|---|
| `source/` | The original meshes, unchanged: lower and upper part, screw halves, knurled head |
| `models/phone_clamp_lower.py` | The lower part (base) with a snap-on channel for the profile under the sole |
| `models/phone_clamp_upper.py` | The upper (moving) jaw without the tripod-nut plate |
| `models/mesh_solid.py` | Loads an STL as a CadQuery solid (cached as `.brep` next to the STL) |
| `export/` | All clamp parts in print orientation (`../export_stl.py`) |

## Changes to the original

- **Upper jaw**: the 38 × 20 mm plate with the blind Ø12 hole for the tripod
  nut is cut off, together with the slope behind it. The centre of the jaw is
  rebuilt from its own exposed surfaces: the front is an arc of R 188 mm in
  plan and R 41.1 mm in profile with a chamfer at the bottom, the top is a
  cylinder of R 38.6 mm. The step at the seam is ~0.03 mm.
- **Base**: a channel for the profile underneath, along the screw axis. The
  knurled screw head hangs 3 mm below the sole (from the jaw and 11 mm beyond
  the end of the part), so the channel ceiling is lowered by a `head_gap`
  spacer of 3.5 mm, and under the head the channel stays open — the profile
  passes under it.
- The screw halves and the knurled head are only re-oriented for printing.

Reference print: both parts, the screw halves and the head standing up;
PLA 230 °C, 0.15 mm layers, 80 % of a fast PLA profile's speeds, 5 mm brim.
