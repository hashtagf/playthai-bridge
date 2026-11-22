package dev.ps5thaisub.overlay

import org.junit.Assert.*
import org.junit.Test
import java.net.HttpURLConnection
import java.net.URL

class CaptionTest {
    private val token = "unit-test-token-24-characters"
    private fun json(id: String = "test", text: String = "เราต้องออกจากที่นี่ก่อนรุ่งสาง", duration: Int = 1000) =
        """{"id":"$id","text":"$text","language":"th","duration_ms":$duration,"created_at":"1990-01-01T00:00:00Z"}"""
    @Test fun expiryIsMonotonicAndDuplicatesDoNotExtendIt() {
        var time = 100L
        val state = CaptionState { time }
        val caption = Caption.parse(json())
        assertTrue(state.accept(caption)); assertEquals(caption.text, state.visible())
        time = 900; assertFalse(state.accept(caption))
        time = 1100; assertEquals("", state.visible())
        assertTrue(state.accept(Caption("next", "replacement", 1000)))
        assertEquals("replacement", state.visible())
        assertTrue(state.accept(Caption("hide", "", 1000))); assertEquals("", state.visible())
    }
    @Test fun validatesPayloads() {
        for (body in listOf(json(duration = 0), json(text = "x".repeat(501)), json(id = "bad id"), json().replace("\"th\"", "\"en\""), json().replace("1000", "1000.5"))) {
            try { Caption.parse(body); fail("accepted invalid caption") } catch (_: IllegalArgumentException) {}
        }
    }
    @Test fun authentication() {
        assertFalse(authorized(null, token)); assertFalse(authorized("Bearer wrong", token))
        assertTrue(authorized("Bearer $token", token))
    }
    @Test fun httpIntegrationAuthUtf8DedupAndExpiry() {
        var clock = 0L; var count = 0
        val state = CaptionState { clock }
        CaptionServer(token, state, { count++ }, "127.0.0.1", 0).use { server ->
            fun request(body: String?, auth: String = token): Pair<Int, String> {
                val conn = URL("http://127.0.0.1:${server.localPort}/${if (body == null) "health" else "v1/captions"}").openConnection() as HttpURLConnection
                conn.connectTimeout = 2000; conn.readTimeout = 2000
                conn.setRequestProperty("Authorization", "Bearer $auth")
                if (body != null) {
                    conn.requestMethod = "POST"; conn.doOutput = true
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                }
                val status = conn.responseCode
                val response = (if (status < 400) conn.inputStream else conn.errorStream).bufferedReader().readText()
                conn.disconnect(); return status to response
            }
            assertEquals(401, request(json(), "wrong").first)
            assertEquals(200, request(null).first)
            assertEquals(202, request(json()).first)
            assertEquals("เราต้องออกจากที่นี่ก่อนรุ่งสาง", state.visible())
            assertEquals(200, request(json()).first); assertEquals(1, count)
            clock = 1000; assertEquals("", state.visible())
            assertEquals(400, request(json(duration = -1)).first)
            assertEquals(413, request("x".repeat(8200)).first)
        }
    }
}
