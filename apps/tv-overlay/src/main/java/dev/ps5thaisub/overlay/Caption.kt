package dev.ps5thaisub.overlay

import org.json.JSONObject
import java.time.OffsetDateTime
import java.security.MessageDigest
import java.net.InetAddress

data class Caption(val id: String, val text: String, val duration: Long) {
    companion object {
        fun parse(body: String): Caption {
            val obj = JSONObject(body)
            require(obj.keys().asSequence().toSet() == setOf("id", "text", "language", "duration_ms", "created_at"))
            require(obj.get("id") is String && obj.get("text") is String && obj.get("created_at") is String)
            val id = obj.getString("id"); val text = obj.getString("text")
            require(id.matches(Regex("[A-Za-z0-9._-]{1,64}")))
            require(text.length <= 500 && text.none { it.code < 32 && it != '\n' })
            require(obj.get("language") == "th")
            val duration = obj.get("duration_ms")
            require(duration is Int || duration is Long)
            val ms = (duration as Number).toLong(); require(ms in 250..15000)
            OffsetDateTime.parse(obj.getString("created_at"))
            return Caption(id, text, ms)
        }
    }
}

class CaptionState(private val now: () -> Long) {
    private val seen = LinkedHashMap<String, Long>()
    var current: Caption? = null; private set
    private var deadline = 0L
    @Synchronized fun accept(caption: Caption): Boolean {
        val time = now()
        seen.entries.removeAll { time - it.value >= 60000 }
        if (seen.containsKey(caption.id)) return false
        seen[caption.id] = time
        if (seen.size > 256) seen.remove(seen.keys.first())
        current = caption; deadline = time + caption.duration
        return true
    }
    @Synchronized fun visible(): String = if (now() < deadline) current?.text ?: "" else ""
}

fun authorized(actual: String?, token: String): Boolean = token.length >= 24 &&
    MessageDigest.isEqual((actual ?: "").toByteArray(), "Bearer $token".toByteArray())
fun lanPeer(address: InetAddress): Boolean = address.isLoopbackAddress || address.isSiteLocalAddress
