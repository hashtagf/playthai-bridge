import AppKit
import ScreenCaptureKit
import Vision
import Foundation

func emit(_ value: Any) throws {
    let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}
func recognize(_ image: CGImage) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([request])
    let lines = (request.results ?? []).filter { ($0.topCandidates(1).first?.confidence ?? 0) >= 0.6 }
        .sorted { a, b in
            if abs(a.boundingBox.midY - b.boundingBox.midY) < 0.02 { return a.boundingBox.minX < b.boundingBox.minX }
            return a.boundingBox.midY > b.boundingBox.midY
        }
    return lines.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
}
@main struct OCR {
    static func main() async {
        do { try await run() }
        catch {
            // OS errors may include private titles or paths. Keep output redacted.
            try? emit(["error": "Capture/OCR failed. Check Screen Recording permission and keep the selected window open, visible and not minimized."])
            exit(1)
        }
    }
    @MainActor static func run() async throws {
        let args = Array(CommandLine.arguments.dropFirst())
        if args == ["--permission"] {
            let granted = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
            try emit(["granted": granted]); return
        }
        if args == ["--capture-self-test"] {
            guard CGPreflightScreenCaptureAccess() else { try emit(["error": "Screen Recording permission required"]); exit(3) }
            let app = NSApplication.shared
            app.setActivationPolicy(.accessory)
            let window = NSWindow(contentRect: NSRect(x: 80, y: 80, width: 1200, height: 600),
                styleMask: [.borderless], backing: .buffered, defer: false)
            window.backgroundColor = .black
            let label = NSTextField(labelWithString: "We have to leave before dawn.")
            label.font = NSFont.systemFont(ofSize: 48); label.textColor = .white
            label.frame = NSRect(x: 30, y: 50, width: 1140, height: 80)
            window.contentView?.addSubview(label)
            let decoy = NSTextField(labelWithString: "THIS MUST NOT BE CAPTURED")
            decoy.font = NSFont.systemFont(ofSize: 32); decoy.textColor = .white
            decoy.frame = NSRect(x: 30, y: 480, width: 1140, height: 60)
            window.contentView?.addSubview(decoy)
            window.orderFrontRegardless()
            defer { window.orderOut(nil) }
            try await Task.sleep(nanoseconds: 300_000_000)
            let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
            guard let selected = content.windows.first(where: { $0.windowID == UInt32(window.windowNumber) }) else { throw NSError(domain: "fixture", code: 1) }
            let config = SCStreamConfiguration(); config.width = 1200; config.height = 600
            config.showsCursor = false; config.ignoreShadowsSingleWindow = true
            let image = try await SCScreenshotManager.captureImage(contentFilter: SCContentFilter(desktopIndependentWindow: selected), configuration: config)
            guard let crop = image.cropping(to: CGRect(x: 0, y: 420, width: 1200, height: 180)) else { throw NSError(domain: "fixture", code: 2) }
            try emit(["text": recognize(crop)]); return
        }
        if args == ["--self-test"] {
            let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1200, pixelsHigh: 180,
                bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
            NSColor.black.setFill(); NSRect(x: 0, y: 0, width: 1200, height: 180).fill()
            ("We have to leave before dawn." as NSString).draw(at: NSPoint(x: 30, y: 60),
                withAttributes: [.font: NSFont.systemFont(ofSize: 48), .foregroundColor: NSColor.white])
            NSGraphicsContext.restoreGraphicsState()
            try emit(["text": recognize(bitmap.cgImage!)]); return
        }
        if args == ["--list"] {
            let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
            let result: [[String: Any]] = windows.filter { ($0[kCGWindowLayer as String] as? Int) == 0 }.map {
                ["id": $0[kCGWindowNumber as String] ?? 0, "app": $0[kCGWindowOwnerName as String] ?? "",
                 "title": $0[kCGWindowName as String] ?? ""]
            }
            try emit(result); return
        }
        guard args.count == 5, let id = UInt32(args[0]),
            let x = Double(args[1]), let y = Double(args[2]), let w = Double(args[3]), let h = Double(args[4]),
            x >= 0, y >= 0, w > 0, h > 0, x+w <= 1, y+h <= 1 else {
            try emit(["error": "Usage: ocr WINDOW_ID X Y WIDTH HEIGHT (normalized top-left region)"]); exit(2)
        }
        guard CGPreflightScreenCaptureAccess() else {
            try emit(["error": "Screen Recording permission required. Run ps5-thai-sub ocr-permission, allow the launching app in macOS Settings, then restart it."]); exit(3)
        }
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        guard let window = content.windows.first(where: { $0.windowID == id && $0.isOnScreen }) else {
            try emit(["error": "Selected window closed or minimized; select Remote Play again."]); exit(4)
        }
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = min(2560, Int(window.frame.width * 2))
        config.height = max(1, Int(Double(config.width) * window.frame.height / window.frame.width))
        config.showsCursor = false
        config.ignoreShadowsSingleWindow = true
        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        let crop = CGRect(x: x * Double(image.width), y: y * Double(image.height),
            width: w * Double(image.width), height: h * Double(image.height)).integral
        guard let cropped = image.cropping(to: crop) else { throw NSError(domain: "crop", code: 1) }
        try emit(["text": recognize(cropped)])
    }
}
