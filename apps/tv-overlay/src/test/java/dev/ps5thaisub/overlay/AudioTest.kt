package dev.ps5thaisub.overlay

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import java.util.Base64
import java.net.HttpURLConnection
import java.net.URL

class AudioTest {
    private fun json(action: String = "chunk", sequence: Long = 1) = JSONObject().put("action", action)
        .put("session", "test-session").put("sequence", sequence).put("sample_rate", 16000)
        .put("channels", 1).put("format", "s16le")
        .put("pcm", Base64.getEncoder().encodeToString(ByteArray(3200))).toString()
    @Test fun validatesFixedAudioFormatAndBounds() {
        assertEquals(3200, AudioPacket.parse(json()).pcm.size)
        for (bad in listOf(json().replace("16000", "48000"), json().replace("s16le", "float"), json(sequence = -1), JSONObject(json()).put("pcm", "AA==").toString())) {
            try { AudioPacket.parse(bad); fail("invalid PCM accepted") } catch (_: IllegalArgumentException) {}
        }
    }
    @Test fun rejectsReplaysAndExpiresDisconnectedSession() {
        var clock = 0L
        val state = AudioSession { clock }
        assertFalse(state.accept(AudioPacket.parse(json())))
        assertTrue(state.accept(AudioPacket.parse(json("start", 0))))
        assertTrue(state.accept(AudioPacket.parse(json())))
        assertFalse(state.accept(AudioPacket.parse(json())))
        assertFalse(state.accept(AudioPacket.parse(json("start", 0))))
        clock = 749; assertFalse(state.expire())
        clock = 750; assertTrue(state.expire()); assertNull(state.id)
        assertFalse(state.accept(AudioPacket.parse(json(sequence = 2))))
        assertTrue(state.accept(AudioPacket.parse(json("start", 0))))
        assertTrue(state.accept(AudioPacket.parse(json("stop", 1))))
        assertNull(state.id)
    }
    @Test fun audioHttpIsAuthenticatedAndBounded() {
        val token = "unit-test-token-24-characters"
        var received = 0
        CaptionServer(token, CaptionState { 0 }, {}, "127.0.0.1", 0,
            onAudio = { received++; it.action != "stop" }).use { server ->
            fun post(body: String, auth: String = token): Int {
                val c = URL("http://127.0.0.1:${server.localPort}/v1/audio").openConnection() as HttpURLConnection
                c.connectTimeout = 2000; c.readTimeout = 2000; c.requestMethod = "POST"; c.doOutput = true
                c.setRequestProperty("Authorization", "Bearer $auth")
                c.setRequestProperty("Content-Type", "application/json")
                c.outputStream.use { it.write(body.toByteArray()) }
                val code = c.responseCode; c.disconnect(); return code
            }
            assertEquals(401, post(json(), "wrong")); assertEquals(0, received)
            assertEquals(202, post(json())); assertEquals(1, received)
            assertEquals(409, post(json("stop", 2)))
            assertEquals(400, post(json().replace("16000", "8000")))
            assertEquals(413, post("x".repeat(8193)))
        }
    }
}
