# Easy Scanner v0.1

A hand-held laser line scanner built around an Android phone: the phone's
camera, a cheap line laser clamped next to it, and a printed ChArUco board as
the world anchor. The phone finds its own pose from the board, triangulates
the laser stripe against a calibrated laser plane and accumulates a coloured
point cloud in millimetres — all on the device, in real time. It can also take
posed full-resolution photos alongside the scan, so the photogrammetry
pipeline of [Orbiter](https://github.com/RawMechatronicsOrg/Orbiter) turns a
session into a textured mesh.

This is **not a finished product**. It's a kit of working pieces — an Android
app and printable parts — so other people can build something similar without
re-deriving everything from scratch. Adapt it to whatever phone, laser and
profile you have on the shelf.

**Status of v0.1**: the app is verified end to end on the emulator (engine
end-to-end tests: camera position within 0.07–1.3 mm at ~500 mm, laser plane
within 0.005°); testing on a real phone is in progress. The parts are being
printed and assembled; the complete scanner has not been debugged as a whole
yet.

## What you need

- An Android phone, Android 10 (API 29) or newer, arm64.
- A line laser module, Ø12 mm body (red or green).
- A 16 × 13 mm aluminium profile — the scanner's frame.
- An M5 × 25 socket head cap screw and an M5 tap (for the ball).
- The printed parts from [`cad/`](cad/README.md) (PLA is fine).
- A ChArUco board, printed flat: by default 8 × 8 squares of 45 mm, 33.3 mm
  markers, dictionary DICT_5X5_100 (any other size can be set in the app's
  Settings).

## Quick start

1. **Print the parts**: `cad/export/` (ball-head laser mount) and
   `cad/phone-clamp/export/` (phone clamp). Print orientations and settings
   are in [cad/README.md](cad/README.md).
2. **Assemble**: clamp the phone and the laser mount onto the profile, put
   the laser into the ring, tilt the ball so the stripe crosses the camera's
   view, tighten the nut.
3. **Build and install the app** ([android/README.md](android/README.md) →
   Toolchain):
   ```powershell
   cd android
   .\gradlew assembleDebug
   adb install app\build\outputs\apk\debug\app-debug.apk
   ```
4. **Calibrate the camera** (Camera mode): lock the focus in Settings, press
   Start and move the board slowly through the frame until it says SAVED.
5. **Calibrate the laser plane** (Laser mode): Start, then sweep the stripe
   across the board at varied tilts.
6. **Scan** (Scan mode): put the object on the board, Start and sweep the
   laser over it; Export writes a binary PLY in the board frame. **Photos ▶**
   adds posed keyframes to an Orbiter photo session for `orbiter-recon`.

## Repository map

```
EasyScanner/
├── README.md        ← you are here
├── LICENSE          ← Apache-2.0 (default for source code)
├── android/         ← the Android app: Kotlin UI + Rust core (OpenCV ChArUco, laser, geometry)
└── cad/             ← printable parts, CadQuery sources + STL
    ├── LICENSE      ← CERN-OHL-S-2.0 (hardware)
    └── phone-clamp/ ← the phone clamp, a remix of a third-party model
        └── LICENSE  ← CC BY-NC-SA 4.0
```

## License

| What                                                     | License                                       |
|----------------------------------------------------------|-----------------------------------------------|
| Source code (Android app, Rust core, scripts, configs)   | [Apache-2.0](LICENSE)                         |
| Hardware designs in `cad/` (CadQuery models, `export_stl.py`, STL) | [CERN-OHL-S-2.0](cad/LICENSE)  |
| The phone clamp in `cad/phone-clamp/`                    | [CC BY-NC-SA 4.0](cad/phone-clamp/LICENSE)    |

The phone clamp is [Tripod Mobile Phone Clamp V2](https://www.printables.com/model/25969-tripod-mobile-phone-clamp-v2)
by Stamos, remixed for the scanner; it keeps its original non-commercial
share-alike licence. Files outside `cad/` are covered by the root `LICENSE`
(Apache-2.0).
