package dev.ps5thaisub.overlay

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.SystemClock

/** Single bounded AudioTrack; no queued utterances, audio-focus stealing or microphone access. */
class AudioPlayback : AutoCloseable {
    private val session = AudioSession { SystemClock.elapsedRealtime() }
    private var track: AudioTrack? = null
    private var previous = -1L
    var enabled = false; private set
    @Volatile var status = "Audio OFF"; private set

    @Synchronized fun enable(value: Boolean) {
        enabled = value
        release()
        status = if (enabled) "Audio ready" else "Audio OFF"
    }
    private fun release() {
        track?.let { runCatching { it.pause(); it.flush() }; runCatching { it.release() } }
        track = null; session.reset(); previous = -1
    }
    @Synchronized fun tick() {
        if (session.expire()) { release(); status = "Audio idle (stream expired)" }
    }
    @Synchronized fun receive(packet: AudioPacket): Boolean {
        if (!enabled) return false
        tick()
        if (!session.accept(packet)) return false
        try {
            when (packet.action) {
                "start" -> {
                    track?.let { it.pause(); it.flush(); it.release() }; track = null
                    val minimum = AudioTrack.getMinBufferSize(16000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
                    require(minimum in 1..16000)
                    track = AudioTrack.Builder()
                        .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                        .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                        .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(maxOf(minimum, 6400)).build()
                    require(track?.state == AudioTrack.STATE_INITIALIZED)
                    track!!.setVolume(0.7f); track!!.play()
                    previous = packet.sequence; status = "Audio streaming"
                }
                "stop" -> { release(); status = "Audio ready" }
                "chunk" -> {
                    val t = track ?: return false
                    if (packet.sequence != previous + 1) { t.pause(); t.flush(); t.play() }
                    previous = packet.sequence
                    val written = t.write(packet.pcm, 0, packet.pcm.size, AudioTrack.WRITE_NON_BLOCKING)
                    if (written != packet.pcm.size) {
                        t.pause(); t.flush(); t.play()
                        status = "Audio chunk dropped (device busy)"
                    } else status = "Audio streaming"
                }
            }
            return true
        } catch (_: Exception) { release(); status = "Audio unavailable on this device"; return false }
    }
    @Synchronized override fun close() { release(); enabled = false }
}
