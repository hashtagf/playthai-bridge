package dev.ps5thaisub.overlay

import android.app.*
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.*
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.TextView

class OverlayService : Service() {
    companion object {
        @Volatile var status = "Stopped"
        @Volatile var running = false
        @Volatile var audioStatus = "Audio OFF"
        const val THAI = "เราต้องออกจากที่นี่ก่อนรุ่งสาง"
    }
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var wm: WindowManager
    private var caption: TextView? = null
    private val expire = Runnable { hide() }
    private var server: CaptionServer? = null
    private val audio = AudioPlayback()
    private val audioWatchdog = object : Runnable {
        override fun run() {
            audio.tick(); audioStatus = audio.status
            handler.postDelayed(this, 250)
        }
    }
    private val pending = java.util.concurrent.atomic.AtomicReference<Caption?>(null)
    private val drain = Runnable { pending.getAndSet(null)?.let { show(it.text, it.duration) } }
    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("subtitles", "Subtitle overlay", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        startForeground(1, Notification.Builder(this, "subtitles").setContentTitle("Thai subtitle overlay active").setContentText("Open app to stop").setSmallIcon(android.R.drawable.ic_menu_info_details).setContentIntent(open).build())
        wm = getSystemService(WindowManager::class.java)
        running = true; status = "Running • local test ready"
        handler.post(audioWatchdog)
        try {
            server = CaptionServer(getSharedPreferences("settings", MODE_PRIVATE).getString("token", "") ?: "",
                CaptionState { SystemClock.elapsedRealtime() }, { item ->
                    pending.set(item)
                    handler.removeCallbacks(drain)
                    handler.post(drain)
                }, onAudio = { audio.receive(it) })
            status = "Running • LAN port 8765"
        } catch (_: Exception) { status = "Local overlay ready; LAN port unavailable (restart service)" }
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!Settings.canDrawOverlays(this)) { status = "Overlay permission missing"; stopSelf(); return START_NOT_STICKY }
        when (intent?.action) {
            "audio-on" -> audio.enable(true)
            "audio-off" -> audio.enable(false)
            "test" -> show(THAI, 30000)
            "hide" -> hide()
            "style" -> caption?.let { style(it) }
        }
        return START_NOT_STICKY
    }
    private fun style(view: TextView) {
        val prefs = getSharedPreferences("settings", MODE_PRIVATE)
        view.textSize = prefs.getInt("size", 32).toFloat()
        view.setBackgroundColor(Color.argb(prefs.getInt("opacity", 65) * 255 / 100, 0, 0, 0))
        val params = WindowManager.LayoutParams((resources.displayMetrics.widthPixels * .85).toInt(), WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT)
        params.gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
        params.y = resources.displayMetrics.heightPixels * prefs.getInt("safe", 10) / 100
        if (view.parent == null) wm.addView(view, params) else wm.updateViewLayout(view, params)
    }
    private fun show(text: String, duration: Long) {
        handler.removeCallbacks(expire)
        if (text.isEmpty()) { hide(); return }
        try {
            val view = caption ?: TextView(this).apply { setTextColor(Color.WHITE); gravity = Gravity.CENTER; setPadding(20, 8, 20, 8); maxLines = 4 }
            view.text = text; style(view); caption = view
            handler.postDelayed(expire, duration)
        } catch (_: RuntimeException) { status = "Overlay rejected by device"; hide() }
    }
    private fun hide() { handler.removeCallbacks(expire); caption?.let { if (it.parent != null) wm.removeView(it) }; caption = null }
    override fun onDestroy() { server?.close(); audio.close(); audioStatus = "Audio OFF"; handler.removeCallbacksAndMessages(null); hide(); running = false; status = "Stopped"; super.onDestroy() }
    override fun onBind(intent: Intent?): IBinder? = null
}
