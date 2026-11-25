package dev.ps5thaisub.overlay

import org.json.JSONObject
import java.util.Base64

data class AudioPacket(val action: String, val session: String, val sequence: Long, val pcm: ByteArray) {
    companion object {
        fun parse(body: String): AudioPacket {
            val j = JSONObject(body)
            val action = j.getString("action")
            require(action in listOf("start", "chunk", "stop"))
            val session = j.getString("session")
            require(session.matches(Regex("[A-Za-z0-9-]{1,64}")))
            val raw = j.get("sequence")
            require(raw is Int || raw is Long)
            val sequence = (raw as Number).toLong(); require(sequence >= 0)
            require(j.getInt("sample_rate") == 16000 && j.getInt("channels") == 1 && j.getString("format") == "s16le")
            val pcm = if (action == "chunk") Base64.getDecoder().decode(j.getString("pcm")) else byteArrayOf()
            require(action != "chunk" || pcm.size == 3200) // exactly 100ms, mono PCM16
            return AudioPacket(action, session, sequence, pcm)
        }
    }
}

/** Session/sequence guard is independent of the Android audio driver for deterministic tests. */
class AudioSession(private val clock: () -> Long) {
    var id: String? = null; private set
    private var sequence = -1L
    private var deadline = 0L
    fun expire(): Boolean {
        if (id != null && clock() >= deadline) { reset(); return true }
        return false
    }
    fun reset() { id = null; sequence = -1; deadline = 0 }
    fun accept(packet: AudioPacket): Boolean {
        expire()
        if (packet.action == "start") {
            // Replayed starts must not reset playback or the sequence guard.
            if (packet.session == id) return false
            id = packet.session; sequence = packet.sequence; deadline = clock() + 750
            return true
        }
        if (packet.session != id || packet.sequence <= sequence) return false
        sequence = packet.sequence
        if (packet.action == "stop") reset() else deadline = clock() + 750
        return true
    }
}
