# Easy Scanner — Android app

A one-camera laser line scanner that runs entirely on the phone: the phone's
camera, a line laser rigidly mounted to it, and a ChArUco board as the world
anchor. It is a native port of an earlier desktop prototype (Python + OpenCV,
not part of this repository), which is why some file formats and tuning units
below are described as "the desktop prototype's".

The screen leads through the steps a scan needs — Board (pick the printed
board, confirm it in view; markers seen without corners say the settings do
not match the print), Focus (lock the lens where autofocus settled, or at the
saved calibration's focus), Camera, Laser plane, Scan, Saved — each one done
when its state holds (`Wizard.kt`: a confirmed board, a locked focus, a
calibration at that focus, a plane fitted with that calibration), so a step
whose prerequisite breaks comes back by itself. Settings → Expert mode shows
the four tool modes underneath instead:

| mode | does |
|------|------|
| **View** | ChArUco pose overlay (grid, outline, axes, working volume) + 6-DOF pose, reprojection RMS, pose-flip margin, focus |
| **Camera** | live intrinsics calibration from varied board views, solved in the background, gated on RMS and plausibility |
| **Laser** | laser-plane calibration: on-board stripes at varied tilts → RANSAC plane `n·X = d` (camera frame) |
| **Scan** | triangulate the stripe against the plane, keep points inside the working volume, accumulate in the board frame, export PLY; **Photos** takes posed full-resolution keyframes for the photogrammetry pass |

How the phone's position in the world is determined is deliberately left
open: today it is the ChArUco board pose (IPPE + temporal disambiguation),
produced in one place (`core/android/src/board.rs`) so another source can
replace it.

## Layout

```
android/
  app/                    Android app (Kotlin): Camera2, resolution governor, overlay, UI
  core/                   Rust workspace
    algo/                 pure Rust, host-testable: laser detector, geometry, plane fit,
                          stripe reconstruction, volume ROI, overlay geometry, focus,
                          point cloud + PLY, config and calibration file formats
    android/              cdylib libeasyscanner_core.so: OpenCV ChArUco + PnP +
                          calibrateCamera, the per-frame engine, JNI bridge
```

Data flow per frame, all on one processing thread:

```
Camera2 YUV_420_888 ──(direct ByteBuffers, no copy)──▶ nativeProcess
  luma plane wrapped as cv::Mat ─▶ CharucoDetector (tracking ROI) ─▶ solvePnPGeneric IPPE
  YUV planes ─▶ laser response inside the projected volume (rayon bands)
            ─▶ per-line peaks + centroids ─▶ chains ─▶ board-plane / laser-plane rays
  ─▶ float[] header + layers ──▶ TripleBuffer ──▶ OverlayView (drawn in place) + HUD
```

## Performance design

- **No pixel copies or colour conversion.** ArUco runs on the luma plane wrapped
  in place. The laser response is computed straight from YUV: the desktop prototype's
  HSV `S·V/255` equals the chroma `max − min` of the clamped RGB, and its hue
  window reduces to integer comparisons, so there is no HSV pass. Chroma is
  upsampled with libjpeg's 9/3/3/1 triangle filter so the stripe centroid keeps
  sub-pixel precision (nearest-neighbour chroma would quantise it to 2-px
  blocks).
- **Only the working volume is scanned.** With a pose, the laser search covers
  the projected cube's convex hull, rasterised to row spans; rows run in
  parallel bands (rayon), allocation-free once warmed up.
- **Board tracking ROI.** After a hit the next search is a padded window around
  the board; a miss, a resolution switch, or every 15th frame falls back to the
  full frame. OpenCV's ArUco3 fast mode is available in Settings but **off by
  default**: it loses small boards outright (a 280-px board at 640x480 gave 0
  corners vs 46 without it), and small boards are exactly what the resolution
  governor produces.
- **Hardware preview.** The preview is a separate Camera2 stream composited by
  the GPU; the CPU only sees the analysis stream. It streams at the analysis
  size whenever the camera can: some HALs scale only to the largest stream and
  cut the smaller ones from its top-left corner (a Galaxy A23 gave a 640x480
  YUV that held 640x480 pixels of the 1440x1080 preview — the board and the
  laser landed in the wrong place on the overlay), so no stream may be larger
  than the analysis one. The photo JPEG stream does not have this effect.
- **Zero-copy results.** The core writes one `float[]` (header + layers in frame
  pixels) into a triple buffer; the overlay draws the floats directly with a
  single rotate/scale matrix.
- **Auto resolution.** `ResolutionGovernor` measures processing time per frame
  (p80 over 1 s windows) and remembers it per size. It steps down when p80
  exceeds 92 % of the frame budget (straight to the first size expected to fit
  in 80 %), and steps up when the larger size is remembered to fit in 85 % or,
  unmeasured, as a probe when the current size leaves real headroom (≤ 60 %).
  A failed probe is remembered for 60 s, so there is no oscillation. It measures
  rather than extrapolating "time ∝ pixels" because fixed per-frame costs make
  that badly pessimistic at small sizes. Only sizes with the sensor's aspect
  ratio that the camera can deliver at the target fps are candidates. It locks
  while the camera calibration collects views (one resolution per solve). A
  frame rate held back by the camera itself (long exposure) is reported, not
  "fixed" by shrinking.

## Calibration notes

- All analysis sizes share the sensor's aspect ratio, so Camera2 scales them
  from the same crop and a calibration taken at one size is **exact** at every
  other (pixel-centre scaling). The desktop prototype had to guess across the
  stills / video crop mismatch.
- Before calibration the core uses the vendor's `LENS_INTRINSIC_CALIBRATION`
  when the phone reports it, else focal length ÷ sensor width. A principal
  point far off the centre is taken as unset and replaced by the centre (the
  Galaxy A23 reports `[3125, 3125, 0, 0, 0]`).
- Video stabilisation, OIS and distortion correction are switched off when the
  camera allows it, so the image geometry stays fixed.
- Lock focus (Settings → Camera → Manual focus) before calibrating: the focal
  length breathes with focus. The focus is stored with the calibration and the
  HUD warns when it differs.
- Calibration files keep the desktop prototype's formats, in the app's files dir:
  `live_intrinsics.json` (plus `camera_id`, `focus_diopters`, `rms_px`) and
  `laser_plane.json` (plus `camera_id` and `k`, the camera model it was
  fitted with); a file taken with another camera is ignored, and a plane
  whose `k` is not the current calibration (or that has none, as the desktop
  prototype's) is kept but not used — the stripe rays it was fitted from
  changed with the camera model. Expert-mode Export writes to
  `/sdcard/Android/data/com.rawmechatronics.easyscanner/files/scans/scan_<time>.ply`
  (binary PLY, XYZ mm + RGB, Z up: the board frame turned 180° about its X
  axis and shifted by the board height, so the object stands on +Z over
  [0, W] × [0, H]; OpenCV's own board +Z points into the board); a copy goes to
  `Download/EasyScanner/` and the share sheet opens with it. The originals:

  ```
  adb pull /sdcard/Android/data/com.rawmechatronics.easyscanner/files/scans/
  ```

  Or keep a computer in sync: [`tools/pull-scans.ps1`](tools/pull-scans.ps1)
  copies new scans and photo sessions into `~\EasyScanner\{scans,sessions}`,
  over USB or, after `adb tcpip 5555`, over Wi-Fi (`-Watch` repeats every
  20 s). It never deletes anything on the phone.

## Photo keyframes → dense mesh and texture

Every guided scan runs in a session (expert mode: **Scan → Photos ▶**); with
Settings → Photos → *Take photos during every scan* off it keeps only the
cloud. The scan's cloud goes into the session as `laser.ply` (native frame)
and `scan.ply` (Z up) on every pause, whenever the app leaves the screen
(the session stays open and carries on after the resume) and on Finish,
which also copies the session to `Download/EasyScanner/<id>/` through
MediaStore (`SessionExport.kt`; an `exported.json` marker remembers it). A
session that never got there — the process was killed — is offered for
copying on the next start; a session is deleted only when nothing was
captured, or on Discard. In a session the phone takes a
full-resolution still on its own, either every N seconds or once the camera
has moved / turned far enough since the last one (Settings → Photos; long
press on the button takes one at the next steady frame). A due keyframe waits
while the board is out of view, the pose fits badly or rests on fewer than 12
corners, or the camera moves faster than the blur limits (measured over
200 ms, shown in the HUD). A still that fails (capture, disk, no pose at its
exposure) is retried after 3 s; five failures in a row close the session.

- **Exact pose.** The still is captured in one request with the preview and
  the analysis stream, so the analysis frame of the same exposure has the same
  sensor timestamp. `PoseTrack` (`core/algo/src/keyframe.rs`) keeps the last
  ~2 s of frames by timestamp: a still gets its own frame's ChArUco pose, or —
  when the processing thread skipped that frame — the pose interpolated
  between its neighbours (≤ 140 ms apart, slerp + straight centre; the row
  says `easyscanner:interpolated`). No board at the exposure → the still is
  dropped.
- **Same camera model.** JPEG sizes must have exactly the analysis stream's
  aspect (Camera2 crops each stream to its own aspect, so only an equal one is
  the same crop; a calibrated session refuses anything else), stills keep the
  raw sensor orientation, and focus / exposure / stabilisation-off are the
  stream's own, so the calibrated K scales to the still exactly. The
  resolution governor is locked for the session.
- **Format = orbiter-native's photo session** (`orbiter.native.photo_session.v1`,
  [`native/orbiter_native/photos.py`](https://github.com/RawMechatronicsOrg/Orbiter/blob/main/native/orbiter_native/photos.py)
  in [Orbiter](https://github.com/RawMechatronicsOrg/Orbiter)), written by `core/algo/src/photo_session.rs`
  into `/sdcard/Android/data/com.rawmechatronics.easyscanner/files/sessions/<yyyyMMdd-HHmmss>/`:

  ```
  session.json          board, frame, volume, one eye "left" with K at the photo size
  photos.jsonl          one row per photo: pose (board->camera, q_wxyz + t_mm), pose rms,
                        corners, sharpness, laser_on / pass_id, sensor timestamp
  photos/left_0001.jpg  the camera's JPEG
  laser.ply             the laser cloud, written when Photos is stopped
  ```

  Everything is in native's board frame: origin at the board centre, +Z out
  of the printed face, +Y up, mm (`geom::FaceOutFrame::centred`). The phone
  is a one-eyed rig (no extrinsics, `pose_gap_*` null). `laser_on` is false
  only when the detector is on and saw no stripe within ±1 s of the exposure;
  recon copies those photos verbatim and prefers them for the atlas, so turn
  the laser off by hand for a clean pass and keep the detector on.
  No `stripe/*.npz` sidecars: recon masks the stripe from the pixels instead
  (its documented fallback).

So the reconstruction is Orbiter's own `orbiter-recon` (Path B in
[`native/docs/PHOTOGRAMMETRY.md`](https://github.com/RawMechatronicsOrg/Orbiter/blob/main/native/docs/PHOTOGRAMMETRY.md);
install it from [`native/`](https://github.com/RawMechatronicsOrg/Orbiter/tree/main/native)):

```
adb pull /sdcard/Android/data/com.rawmechatronics.easyscanner/files/sessions/<id> <dir>
orbiter-recon --session <dir> --mode texture-only   # Poisson mesh of laser.ply + mesh_texturer + GLB
orbiter-recon --session <dir> --mode dense          # + PatchMatch / fusion merged with the laser cloud
```

A session directory that already exists is never written into.
recon needs ≥ 1000 laser points and ≥ 20 selected photos (each seeing the
object fill ≥ 25 % of the frame from 150–500 mm; `views.SelectParams`), so
scan with the laser and take photos in the same session. Changing the board
or the camera, re-calibrating the camera, or (expert mode) leaving Scan mode
closes the session, its files kept.

## Toolchain

Built on Windows; the same steps work on Linux/macOS.

1. Android SDK (build-tools 36.1.0, platform 36) and **NDK 28.2.13676358**
   (`sdkmanager "ndk;28.2.13676358"`), JDK 17+ (Android Studio's `jbr`).
2. Rust ≥ 1.88 with the Android targets:
   `rustup target add aarch64-linux-android x86_64-linux-android`.
3. **libclang** for the `opencv` crate's binding generator. The NDK does not
   ship it; the `libclang` wheel from PyPI does:
   `python -m pip download libclang==18.1.1 --no-deps --only-binary :all: --platform win_amd64`,
   unzip it, and point `local.properties` at `…/platlib/clang/native`:

   ```properties
   sdk.dir=C\:/Users/<you>/AppData/Local/Android/Sdk
   libclang.dir=C\:/path/to/libclang/native
   ```

   (`LIBCLANG_PATH` works too.)

OpenCV itself comes from Maven (`org.opencv:opencv:4.14.0`): Gradle packages its
`libopencv_java4.so`, and the `cargoBuild-<abi>` tasks extract the AAR's prefab
headers for cargo to link against the same library. The Rust build is wired
into `preBuild`:

```
gradlew assembleDebug        # or assembleRelease (signed with the debug key)
gradlew testDebugUnitTest    # Kotlin governor tests
cd core && cargo test -p scan-algo   # Rust algorithm tests (host)
```

The engine's end-to-end tests (`core/android/src/e2e_tests.rs`) render ChArUco
frames from a known pose and laser plane, push them through the engine as YUV
and check the recovered pose, intrinsics and plane. They need OpenCV, so they
run on a device or emulator: build the test binary with the same environment
the Gradle task sets (`cargo test --release --target x86_64-linux-android -p
easyscanner-core --no-run`), then

```
adb push <test binary> /data/local/tmp/es/e2e
adb push app/build/opencv-prefab/libs/android.x86_64/libopencv_java4.so /data/local/tmp/es/
adb push <ndk>/toolchains/llvm/prebuilt/<host>/sysroot/usr/lib/x86_64-linux-android/libc++_shared.so /data/local/tmp/es/
adb shell "cd /data/local/tmp/es && LD_LIBRARY_PATH=. ./e2e --test-threads=1 --nocapture"
```

On the emulator (x86_64, 1280x960): camera position within 0.07–1.3 mm at
~500 mm, reprojection 0.04–0.27 px; a calibration started 8 % off converges to
fx within 0.01 % (rms 0.13 px, ~2 s); the laser plane comes back within
0.005° / 0.01 mm; tracking survives a 1280→640 switch; a `cv::Exception`
surfaces as an `Err` (the opencv wrapper shares `libc++_shared` with
`libopencv_java4.so`).

`easyscanner.abis` in `gradle.properties` selects the ABIs (default
`arm64-v8a`; add `x86_64` for the emulator).

Toolchain gotchas found on the way: the binding generator asks `CLANG_PATH` for
the system include order, so it must be the NDK's `<triple>29-clang++` wrapper
(a host clang puts its builtin headers ahead of libc++ and parsing fails);
`clang-sys` needs the `clang-runtime` feature with a DLL-only libclang; and
`OPENCV_CLANG_ARGS` is shell-split, so Windows paths are passed with forward
slashes.

## Status

- Ported: board detection + pose, live intrinsics calibration, laser detection,
  on-board reconstruction, laser-plane calibration, plane triangulation +
  volume classification, cloud accumulation + PLY export, overlay, HUD.
- Added beyond the desktop prototype: posed photo keyframes in orbiter-native's session
  format (above). Verified: engine e2e on the emulator (still pose 0.2 mm /
  0.02° from truth), orbiter-recon's `write_sparse` accepts a synthetic
  session (all 36 photos selected, laser seeds tracked); the still capture
  itself still needs a run on a real phone.
- On a real phone (2026-10-19): camera calibration, laser-plane calibration
  (rms 0.35 mm) and a scan exported as PLY (254 k points) — screenshots in the
  [main README](../README.md#first-scan-on-a-real-phone).
- Galaxy A23 (SM-A236B, 2026-10-28): the board pose holds at 1440x1080,
  960x720 and 640x480 (57–61 corners, 0.7–1.0 px, the camera position agrees
  within 1 mm across sizes) with the two HAL workarounds above. Keep ArUco3
  off there: it finds 56 corners at 1440x1080 and none at 960x720 or below.
- Not ported: the off-frame virtual margin, PNG snapshots (use the phone's
  screenshot), the Orbiter `orbiter_state.json` lookup (board parameters live in
  Settings; the default is 8x8, 45 mm squares, 33.3 mm markers, DICT_5X5_100).
- Laser colour in the cloud is sampled at the laser pixel (tinted), as in
  the desktop prototype.
