package dev.ps5thaisub.overlay

import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import kotlin.concurrent.thread

/** Small close-after-response HTTP subset. One worker, bounded backlog/body/header/time. */
class CaptionServer(private val token: String, private val state: CaptionState,
                    private val onCaption: (Caption) -> Unit,
                    bind: String = "0.0.0.0", port: Int = 8765,
                    private val onAudio: ((AudioPacket) -> Boolean)? = null) : AutoCloseable {
    private val socket = ServerSocket().apply {
        reuseAddress = true
        bind(InetSocketAddress(InetAddress.getByName(bind), port), 4)
    }
    val localPort: Int get() = socket.localPort
    @Volatile private var active: Socket? = null
    private val worker = thread(name = "caption-http", isDaemon = true) {
        while (!socket.isClosed) {
            try {
                socket.accept().use { client ->
                    active = client
                    client.soTimeout = 1000
                    try { handle(client) } catch (_: Exception) { reply(client, 400, "invalid request") }
                    finally { active = null }
                }
            } catch (_: Exception) { /* shutdown or disconnected client; never log secrets */ }
        }
    }
    private fun reply(client: Socket, status: Int, message: String) {
        val body = "{\"status\":\"$message\"}".toByteArray(Charsets.UTF_8)
        val head = "HTTP/1.1 $status Result\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: ${body.size}\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n"
        client.getOutputStream().apply { write(head.toByteArray()); write(body); flush() }
    }
    private fun handle(client: Socket) {
        if (!lanPeer(client.inetAddress)) { reply(client, 403, "LAN only"); return }
        val input = BufferedInputStream(client.getInputStream())
        val header = ByteArrayOutputStream()
        var suffix = 0
        val started = System.nanoTime()
        while (header.size() < 4096 && suffix != 0x0d0a0d0a) {
            require(System.nanoTime() - started < 2_000_000_000L)
            val byte = input.read(); require(byte >= 0)
            header.write(byte); suffix = (suffix shl 8) or byte
        }
        require(suffix == 0x0d0a0d0a)
        val lines = header.toString("US-ASCII").split("\r\n")
        val request = lines.first().split(" ")
        require(request.size == 3 && request[2] == "HTTP/1.1")
        val headers = mutableMapOf<String, String>()
        for (line in lines.drop(1).filter { it.isNotEmpty() }) {
            val parts = line.split(":", limit = 2); require(parts.size == 2)
            val key = parts[0].lowercase(); require(!headers.containsKey(key))
            headers[key] = parts[1].trim()
        }
        if (!authorized(headers["authorization"], token)) { reply(client, 401, "unauthorized"); return }
        if (headers.containsKey("origin")) { reply(client, 403, "browser origins forbidden"); return }
        require(!headers.containsKey("transfer-encoding"))
        if (request[0] == "GET" && request[1] == "/health") { reply(client, 200, "ok"); return }
        if (request[0] != "POST" || request[1] !in listOf("/v1/captions", "/v1/audio")) { reply(client, 404, "not found"); return }
        require(headers["content-type"]?.substringBefore(';')?.trim() == "application/json")
        val size = headers["content-length"]?.toIntOrNull() ?: -1
        if (size !in 1..8192) { reply(client, 413, "body limit"); return }
        val bytes = ByteArray(size); var count = 0
        while (count < size) {
            require(System.nanoTime() - started < 2_000_000_000L)
            val read = input.read(bytes, count, size - count); require(read > 0); count += read
        }
        val decoder = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
        val body = decoder.decode(ByteBuffer.wrap(bytes)).toString()
        if (request[1] == "/v1/audio") {
            if (onAudio == null) { reply(client, 404, "audio unsupported"); return }
            val accepted = onAudio.invoke(AudioPacket.parse(body))
            reply(client, if (accepted) 202 else 409, if (accepted) "audio accepted" else "audio disabled or session expired")
            return
        }
        val caption = Caption.parse(body)
        if (state.accept(caption)) { onCaption(caption); reply(client, 202, "accepted") }
        else reply(client, 200, "duplicate")
    }
    override fun close() { socket.close(); active?.close(); worker.join(1500) }
}
