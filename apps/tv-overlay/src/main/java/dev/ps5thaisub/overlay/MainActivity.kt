package dev.ps5thaisub.overlay

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.*
import java.net.NetworkInterface
import java.net.Inet4Address
import java.security.SecureRandom

class MainActivity : Activity() {
    private lateinit var status: TextView
    private val handler = Handler(Looper.getMainLooper())
    private val refresh = object : Runnable {
        override fun run() {
            status.text = "Permission: ${Settings.canDrawOverlays(this@MainActivity)} | ${OverlayService.status} | ${OverlayService.audioStatus}"
            handler.postDelayed(this, 1000)
        }
    }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        val prefs = getSharedPreferences("settings", MODE_PRIVATE)
        if (!prefs.contains("token")) {
            val bytes = ByteArray(24); SecureRandom().nextBytes(bytes)
            prefs.edit().putString("token", bytes.joinToString("") { "%02x".format(it) }).apply()
        }
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(40, 16, 40, 16) }
        setContentView(ScrollView(this).apply { addView(layout) })
        fun label(text: String) = TextView(this).apply { this.text = text; textSize = 16f; layout.addView(this) }
        fun button(text: String, action: () -> Unit) { layout.addView(Button(this).apply { this.text = text; setOnClickListener { action() } }) }
        label("PlayThai Bridge • HDMI feasibility test")
        status = label("")
        val ips = NetworkInterface.getNetworkInterfaces().toList().flatMap { it.inetAddresses.toList() }.filter { it is Inet4Address && it.isSiteLocalAddress }.joinToString { it.hostAddress ?: "" }
        label("TV address: $ips :8765 | Token: ${prefs.getString("token", "")}")
        button("Request Overlay Permission") {
            try { startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))) }
            catch (_: android.content.ActivityNotFoundException) { Toast.makeText(this, "Settings unavailable. See optional ADB appops instructions.", Toast.LENGTH_LONG).show() }
        }
        button("Start Service") { command("start") }
        button("Show Thai Test Subtitle") { command("test") }
        button("Hide Subtitle") { command("hide") }
        button("Enable Thai Audio") { command("audio-on") }
        button("Mute Thai Audio") { command("audio-off") }
        button("Stop Service") { stopService(Intent(this, OverlayService::class.java)) }
        val row = LinearLayout(this)
        layout.addView(row)
        fun cycle(name: String, key: String, values: List<Int>, default: Int) {
            row.addView(Button(this).apply {
                fun title() { text = "$name: ${prefs.getInt(key, default)}" }; title()
                setOnClickListener {
                    val value = values[(values.indexOf(prefs.getInt(key, default)) + 1) % values.size]
                    prefs.edit().putInt(key, value).apply(); title()
                    if (OverlayService.running) command("style")
                }
            })
        }
        cycle("Text sp", "size", listOf(24, 32, 40, 48), 32)
        cycle("Opacity %", "opacity", listOf(0, 40, 65, 80), 65)
        cycle("Bottom %", "safe", listOf(5, 10, 15, 20), 10)
        label("Test expires after 30 seconds. Start from this screen. No automatic boot start. Token is private; trusted LAN only.")
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 1)
    }
    private fun command(action: String) {
        if (!Settings.canDrawOverlays(this)) { Toast.makeText(this, "Grant overlay permission first", Toast.LENGTH_LONG).show(); return }
        startForegroundService(Intent(this, OverlayService::class.java).setAction(action))
    }
    override fun onResume() { super.onResume(); handler.post(refresh) }
    override fun onPause() { handler.removeCallbacks(refresh); super.onPause() }
}
