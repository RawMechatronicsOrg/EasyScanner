package com.rawmechatronics.easyscanner

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.SurfaceTexture
import android.hardware.camera2.CameraManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.TextureView
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.constraintlayout.widget.ConstraintLayout
import androidx.core.content.ContextCompat
import androidx.preference.PreferenceManager
import com.rawmechatronics.easyscanner.FrameResult.Calib
import com.rawmechatronics.easyscanner.FrameResult.H
import com.rawmechatronics.easyscanner.FrameResult.Photo
import com.rawmechatronics.easyscanner.databinding.ActivityMainBinding
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The scanner screen: live preview + pose overlay + HUD, and the four modes
 * of the desktop prototype — viewfinder, camera (intrinsics) calibration, laser-plane
 * calibration, and scanning.
 */
class MainActivity : AppCompatActivity(), FrameProcessor.Listener {

    private enum class Mode { VIEW, CAMERA, LASER, SCAN }

    private lateinit var b: ActivityMainBinding
    private lateinit var mgr: CameraManager
    private lateinit var processor: FrameProcessor
    private lateinit var camera: CameraController
    private val main = Handler(Looper.getMainLooper())

    @Volatile private var info: CameraInfo? = null
    @Volatile private var governor: ResolutionGovernor? = null
    private var mode = Mode.VIEW
    private var messages = JSONObject()
    private val fps = FpsMeter()
    private val hudPending = AtomicBoolean(false)

    // last header values the buttons depend on (UI thread)
    private var calibActive = false
    private var planeActive = false
    private var scanOn = false

    /** The open photo session's directory (set on the UI thread, read on the still thread). */
    @Volatile private var photoDir: File? = null
    /**
     * The serial this side gave its photo session. The core echoes the serial
     * of the last session it opened, so "off" with OUR serial means the core
     * closed it, and results from before the session started are told apart.
     */
    private var photoSerial = 0

    // on a grant the activity resumes next, and onResume opens the camera
    private val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) status(getString(R.string.need_camera))
    }

    /** The camera was (re)opened for the current resume; reset by onPause. */
    private var cameraStarted = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityMainBinding.inflate(layoutInflater)
        setContentView(b.root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        mgr = getSystemService(CameraManager::class.java)
        processor = FrameProcessor(filesDir.absolutePath, this)
        camera = CameraController(
            mgr, processor.handler, processor,
            onError = { msg -> main.post { onError(msg) } },
            onSizeFailed = { size -> main.post { fallBackFrom(size) } },
            onStill = ::onStill,
            onStillFailed = { msg, fatal -> main.post { onStillFailed(msg, fatal) } },
        )
        b.overlay.source = processor.results

        b.settingsButton.setOnClickListener { startActivity(Intent(this, SettingsActivity::class.java)) }
        b.modes.check(R.id.modeView)
        b.modes.addOnButtonCheckedListener { _, id, checked ->
            if (checked) setMode(
                when (id) {
                    R.id.modeCamera -> Mode.CAMERA
                    R.id.modeLaser -> Mode.LASER
                    R.id.modeScan -> Mode.SCAN
                    else -> Mode.VIEW
                }
            )
        }
        listOf(b.action1, b.action2, b.action3, b.action4).forEachIndexed { i, btn ->
            btn.setOnClickListener { onAction(i) }
        }
        b.action4.setOnLongClickListener {
            if (mode != Mode.SCAN || photoDir == null) return@setOnLongClickListener false
            processor.command(Cmd.PHOTO_SNAP) { renderStatus() }
            true
        }
        b.texture.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
            override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) = startCamera()
            override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) {}
            override fun onSurfaceTextureDestroyed(st: SurfaceTexture) = true
            override fun onSurfaceTextureUpdated(st: SurfaceTexture) {}
        }
        setMode(Mode.VIEW)
    }

    override fun onResume() {
        super.onResume()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            askCamera.launch(Manifest.permission.CAMERA)
        } else {
            startCamera()
        }
    }

    override fun onPause() {
        // the camera goes away and the settings may change: the session ends here
        if (photoDir != null) stopPhotos()
        camera.close()
        cameraStarted = false
        super.onPause()
    }

    override fun onDestroy() {
        camera.quit()
        processor.release()
        super.onDestroy()
    }

    /** (Re)read the settings and (re)open the camera with them. */
    private fun startCamera() {
        if (cameraStarted || !b.texture.isAvailable || !hasCameraPermission()) return
        cameraStarted = true
        val st = AppSettings.load(this)
        val ids = CameraInfo.backCameraIds(mgr)
        if (ids.isEmpty()) {
            status(getString(R.string.no_camera))
            return
        }
        val inf = CameraInfo.query(mgr, st.cameraId.takeIf { it in ids } ?: ids.first(), st.targetFps, st.maxLongSide)
        info = inf
        val pv = inf.previewSize
        val portrait = inf.sensorOrientation % 180 != 0
        (b.previewFrame.layoutParams as ConstraintLayout.LayoutParams).dimensionRatio =
            if (portrait) "${pv.height}:${pv.width}" else "${pv.width}:${pv.height}"
        b.previewFrame.requestLayout()
        b.overlay.sensorOrientation = inf.sensorOrientation

        processor.configure(st.nativeConfig(inf))
        val sizes = inf.analysisSizes
        governor = if (st.autoResolution) {
            ResolutionGovernor(sizes.map { FrameSize(it.width, it.height) }, st.targetFps, 0)
                .also { it.reset(0, System.nanoTime()) }
        } else null
        camera.open(inf, b.texture.surfaceTexture!!, sizes.first(), st)
        renderButtons()
    }

    /** The camera refused [size]: continue one size smaller and never retry it. */
    private fun fallBackFrom(size: android.util.Size) {
        val sizes = info?.analysisSizes ?: return
        val next = sizes.indexOf(size) + 1
        if (next <= 0 || next > sizes.lastIndex) {
            onError("camera session failed at ${size.width}x${size.height}")
            return
        }
        status("camera refused ${size.width}x${size.height}, using ${sizes[next].width}x${sizes[next].height}")
        processor.handler.post { governor?.limitTo(next, System.nanoTime()) }
        camera.setAnalysisSize(sizes[next])
    }

    private fun hasCameraPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    // ── processing-thread callbacks ──────────────────────────────────────────

    override fun onResult(r: FrameResult) {
        fps.tick(r.timestampNs)
        governor?.let { g ->
            // one size per calibration solve, and per photo session (its stills share one K)
            g.frozen = r.flag(H.CALIB_ACTIVE) || r[H.CALIB_STATE].toInt() == Calib.SOLVING ||
                r[H.PHOTO_STATE].toInt() != Photo.OFF
            val from = g.size
            // frames still in flight from before a switch say nothing about the new size
            if (r[H.FRAME_W].toInt() != from.width || r[H.FRAME_H].toInt() != from.height) return@let
            g.onFrame(r.procMs, System.nanoTime())?.let { idx ->
                info?.analysisSizes?.getOrNull(idx)?.let { size ->
                    Log.i(TAG, "resolution $from -> ${size.width}x${size.height}")
                    camera.setAnalysisSize(size)
                }
            }
        }
        b.overlay.postInvalidateOnAnimation()
        if (hudPending.compareAndSet(false, true)) {
            main.postDelayed({
                hudPending.set(false)
                renderHud()
            }, HUD_PERIOD_MS)
        }
    }

    override fun onPhotoDue() {
        camera.captureStill()
    }

    /** A still is back (still thread): onto disk, then to the core to be posed and named. */
    private fun onStill(s: Still) {
        val file = photoDir?.let { File(it, "photos/.pending_${s.timestampNs}.jpg") } ?: return
        try {
            file.writeBytes(s.jpeg)
        } catch (e: IOException) {
            main.post { onStillFailed("photo not written: ${e.message}", false) }
            return
        }
        val arg = JSONObject().put("file", file.absolutePath).put("ts", s.timestampNs)
            .put("w", s.width).put("h", s.height)
        processor.command(Cmd.PHOTO_ADD, arg.toString())
    }

    /** A still did not happen: the core backs off (and gives up after a few); none possible at all ends the session. */
    private fun onStillFailed(msg: String, fatal: Boolean) {
        if (photoDir == null) return
        status(msg)
        if (fatal) {
            Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
            stopPhotos()
        } else {
            processor.command(Cmd.PHOTO_FAILED, msg) { renderStatus() }
        }
    }

    override fun onMessages(json: String) {
        messages = runCatching { JSONObject(json) }.getOrDefault(messages)
        renderStatus()
    }

    override fun onError(msg: String) {
        status(msg)
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    // ── HUD / buttons ────────────────────────────────────────────────────────

    private fun renderHud() {
        val r = processor.results.latest() ?: return
        fun f(slot: Int) = r[slot]
        fun has(slot: Int) = !f(slot).isNaN()
        val sb = StringBuilder()
        sb.append("%.0fx%.0f  %.1f fps  proc %.1f ms (board %.1f, laser %.1f)\n".format(
            f(H.FRAME_W), f(H.FRAME_H), fps.fps, r.procMs, f(H.T_BOARD_MS), f(H.T_LASER_MS)))
        sb.append(governor?.let { "auto: ${it.status}" } ?: "fixed resolution").append('\n')
        if (r.flag(H.DETECTED)) {
            sb.append("board %d pts  rms %.2f px  margin %s  focus %s\n".format(
                f(H.N_CORNERS).toInt(), f(H.REPROJ_RMS),
                if (has(H.POSE_MARGIN)) "%.1fx".format(f(H.POSE_MARGIN)) else "-",
                if (has(H.FOCUS_PCT)) "%.0f%%".format(f(H.FOCUS_PCT)) else "-"))
            sb.append("cam X %.1f  Y %.1f  Z %.1f mm  d %.0f\n".format(
                f(H.CAM_X), f(H.CAM_Y), f(H.CAM_Z), f(H.DISTANCE)))
            sb.append("    roll %.1f  pitch %.1f  yaw %.1f deg\n".format(f(H.ROLL), f(H.PITCH), f(H.YAW)))
        } else {
            sb.append("board: not found (%d corners)\n".format(f(H.N_CORNERS).toInt()))
        }
        sb.append("K: %s  fx %.0f cx %.0f cy %.0f\n".format(
            messages.optString("intrinsics", "?"), f(H.FX), f(H.CX), f(H.CY)))
        when (f(H.LASER_STATE).toInt()) {
            0 -> sb.append("laser: off")
            1 -> sb.append("laser: none (peak %.0f)".format(f(H.LASER_PEAK)))
            else -> {
                sb.append("laser: %d pts  peak %.0f".format(f(H.LASER_POINTS).toInt(), f(H.LASER_PEAK)))
                if (has(H.LASER_LENGTH)) sb.append("  on board %.0f mm @ %.0f deg".format(f(H.LASER_LENGTH), f(H.LASER_ANGLE)))
                if (f(H.IN_VOLUME) > 0f) sb.append("  in volume %d".format(f(H.IN_VOLUME).toInt()))
            }
        }
        sb.append('\n')
        sb.append("plane: %s  cloud %d pts %.1f MB".format(
            if (r.flag(H.PLANE_OK)) "ok" else "none", f(H.CLOUD_POINTS).toInt(), f(H.CLOUD_MB)))
        val photoState = f(H.PHOTO_STATE).toInt()
        if (photoState != Photo.OFF) {
            sb.append("\nphotos %d  %s".format(f(H.PHOTO_COUNT).toInt(), photoStateLabel(photoState)))
            if (has(H.CAM_SPEED)) sb.append("  moving %.0f mm/s %.1f deg/s".format(f(H.CAM_SPEED), f(H.CAM_TURN)))
        } else if (photoDir != null && f(H.PHOTO_SERIAL).toInt() == photoSerial) {
            // the core closed our session (board or calibration changed, photos kept failing)
            endPhotos()
        }
        when (mode) {
            Mode.CAMERA -> sb.append("\ncalib %d/%d views  last rms %s".format(
                f(H.CALIB_COUNT).toInt(), f(H.CALIB_TARGET).toInt(),
                if (has(H.CALIB_RMS)) "%.2f px".format(f(H.CALIB_RMS)) else "-"))
            Mode.LASER -> sb.append("\nlines %d/%d  spread %.2f  last fit %s".format(
                f(H.PLANE_LINES).toInt(), f(H.PLANE_TARGET).toInt(), f(H.PLANE_SPREAD),
                if (has(H.PLANE_RMS)) "%.2f mm".format(f(H.PLANE_RMS)) else "-"))
            else -> {}
        }
        b.hud.text = sb

        val newCalib = r.flag(H.CALIB_ACTIVE)
        val newPlane = r.flag(H.PLANE_ACTIVE)
        val newScan = r.flag(H.SCAN_ON)
        if (newCalib != calibActive || newPlane != planeActive || newScan != scanOn) {
            calibActive = newCalib
            planeActive = newPlane
            scanOn = newScan
            renderButtons()
        }
    }

    private fun photoStateLabel(state: Int) = when (state) {
        Photo.WAITING -> "waiting"
        Photo.IN_FLIGHT -> "taking..."
        Photo.HOLD_NO_BOARD -> "due: no board"
        Photo.HOLD_POSE_RMS -> "due: pose rms high"
        Photo.HOLD_FEW_CORNERS -> "due: too few board corners"
        Photo.HOLD_SETTLING -> "due: measuring motion"
        Photo.HOLD_MOVING -> "due: hold steady"
        else -> "?"
    }

    private fun setMode(m: Mode) {
        // leaving a mode stops what it was doing
        when (mode) {
            Mode.CAMERA -> if (m != Mode.CAMERA && calibCollecting()) processor.command(Cmd.CALIB_STOP)
            Mode.LASER -> if (m != Mode.LASER && planeActive) processor.command(Cmd.PLANE_STOP)
            Mode.SCAN -> if (m != Mode.SCAN) {
                if (scanOn) processor.command(Cmd.SCAN_STOP)
                if (photoDir != null) stopPhotos()
            }
            Mode.VIEW -> {}
        }
        mode = m
        renderButtons()
        renderStatus()
    }

    private fun calibCollecting() = calibActive

    private fun laserEnabled() = PreferenceManager.getDefaultSharedPreferences(this).getBoolean("laser_enabled", true)

    private fun renderButtons() {
        val labels: List<String?> = when (mode) {
            Mode.VIEW -> listOf(getString(if (laserEnabled()) R.string.act_laser_on else R.string.act_laser_off), null, null, null)
            Mode.CAMERA -> listOf(
                getString(if (calibCollecting()) R.string.act_pause else R.string.act_start),
                getString(R.string.act_capture), getString(R.string.act_reset), getString(R.string.act_forget_k),
            )
            Mode.LASER -> listOf(
                getString(if (planeActive) R.string.act_pause else R.string.act_start),
                getString(R.string.act_force), getString(R.string.act_forget_plane), null,
            )
            Mode.SCAN -> listOf(
                getString(if (scanOn) R.string.act_stop else R.string.act_start),
                getString(R.string.act_export), getString(R.string.act_clear),
                getString(if (photoDir != null) R.string.act_photos_on else R.string.act_photos_off),
            )
        }
        listOf<Button>(b.action1, b.action2, b.action3, b.action4).zip(labels).forEach { (btn, label) ->
            btn.visibility = if (label == null) View.INVISIBLE else View.VISIBLE
            btn.text = label ?: ""
        }
    }

    private fun renderStatus() {
        val (hint, key) = when (mode) {
            Mode.VIEW -> R.string.hint_view to "intrinsics"
            Mode.CAMERA -> R.string.hint_camera to "calib"
            Mode.LASER -> R.string.hint_laser to "plane"
            Mode.SCAN -> R.string.hint_scan to "scan"
        }
        val keys = if (mode == Mode.SCAN) listOf(key, "photos") else listOf(key)
        val msg = keys.map { messages.optString(it, "") }.filter { it.isNotEmpty() }.joinToString("\n")
        status(if (msg.isEmpty()) getString(hint) else "$msg\n\n${getString(hint)}")
    }

    private fun status(text: String) {
        b.status.text = text
    }

    private fun onAction(i: Int) {
        val show: (String) -> Unit = { renderStatus() }
        when (mode) {
            Mode.VIEW -> if (i == 0) {
                val p = PreferenceManager.getDefaultSharedPreferences(this)
                p.edit().putBoolean("laser_enabled", !laserEnabled()).apply()
                processor.configure(AppSettings.load(this).nativeConfig(info))
                renderButtons()
            }
            Mode.CAMERA -> when (i) {
                0 -> processor.command(if (calibCollecting()) Cmd.CALIB_STOP else Cmd.CALIB_START, done = show)
                1 -> processor.command(Cmd.CALIB_CAPTURE, done = show)
                2 -> processor.command(Cmd.CALIB_RESET, done = show)
                3 -> processor.command(Cmd.FORGET_INTRINSICS, done = show)
            }
            Mode.LASER -> when (i) {
                0 -> processor.command(if (planeActive) Cmd.PLANE_STOP else Cmd.PLANE_START, done = show)
                1 -> processor.command(Cmd.PLANE_FORCE, done = show)
                2 -> processor.command(Cmd.FORGET_PLANE, done = show)
            }
            Mode.SCAN -> when (i) {
                0 -> processor.command(if (scanOn) Cmd.SCAN_STOP else Cmd.SCAN_START, done = show)
                1 -> {
                    val dir = File(getExternalFilesDir(null), "scans").apply { mkdirs() }
                    val name = "scan_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date()) + ".ply"
                    processor.command(Cmd.EXPORT_PLY, File(dir, name).absolutePath) { msg ->
                        renderStatus()
                        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
                    }
                }
                2 -> processor.command(Cmd.CLOUD_CLEAR, done = show)
                3 -> if (photoDir == null) startPhotos() else stopPhotos()
            }
        }
    }

    /**
     * Open a photo session (orbiter-native's layout) under the app's files and
     * add the still stream to the camera.
     */
    private fun startPhotos() {
        val inf = info ?: return
        if (inf.stillSizes.isEmpty()) {
            onError(getString(R.string.photos_unavailable))
            return
        }
        val now = Date()
        val id = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(now)
        val utc = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(now)
        val root = File(getExternalFilesDir(null), "sessions")
        // the core refuses an existing directory: a second start within the same second gets a suffix
        val dir = generateSequence(1) { it + 1 }.map { File(root, if (it == 1) id else "$id-$it") }.first { !it.exists() }
        photoDir = dir
        val serial = ++photoSerial
        camera.setStills(inf.stillSizes)
        val arg = JSONObject().put("dir", dir.absolutePath).put("session_id", dir.name)
            .put("started_utc", utc).put("serial", serial)
        processor.command(Cmd.PHOTOS_START, arg.toString()) { msg ->
            renderStatus()
            // engine.rs open_photos: anything else is a refusal
            if (!msg.startsWith("photos on") && photoSerial == serial && photoDir != null) {
                Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
                endPhotos()
            }
        }
        renderButtons()
    }

    private fun stopPhotos() {
        processor.command(Cmd.PHOTOS_STOP) { msg ->
            renderStatus()
            Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
        }
        endPhotos()
    }

    /** Forget the session on this side and give the camera its still stream back. */
    private fun endPhotos() {
        photoDir = null
        camera.setStills(emptyList())
        renderButtons()
    }

    /** Delivered frame rate from sensor timestamps (smoothed). */
    private class FpsMeter {
        @Volatile var fps = 0.0
            private set
        private var last = 0L

        fun tick(ts: Long) {
            if (last != 0L && ts > last) {
                val inst = 1e9 / (ts - last)
                fps = if (fps == 0.0) inst else fps * 0.9 + inst * 0.1
            }
            last = ts
        }
    }

    private companion object {
        const val TAG = "EasyScanner"
        const val HUD_PERIOD_MS = 100L
    }
}
