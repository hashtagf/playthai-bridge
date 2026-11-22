import AppKit
import ScreenCaptureKit
import AVFoundation
import CoreMedia
import CoreImage
import Vision

func event(_ type: String, _ message: String) {
    let data = try! JSONSerialization.data(withJSONObject: ["type": type, "message": message])
    FileHandle.standardError.write(data + Data([10]))
}

final class OCRSink: NSObject, SCStreamOutput {
    let crops: [[Double]]
    let context = CIContext()
    init(_ crops: [[Double]]) { self.crops = crops }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sample.isValid, let buffer = CMSampleBufferGetImageBuffer(sample) else { return }
        let ci = CIImage(cvPixelBuffer: buffer)
        guard let image = context.createCGImage(ci, from: ci.extent) else { return }
        do {
            var texts: [String] = []
            for c in crops {
                let rect = CGRect(x: c[0] * Double(image.width), y: c[1] * Double(image.height),
                    width: c[2] * Double(image.width), height: c[3] * Double(image.height)).integral
                guard let crop = image.cropping(to: rect) else { throw NSError(domain: "crop", code: 1) }
                let request = VNRecognizeTextRequest()
                request.recognitionLevel = .accurate; request.recognitionLanguages = ["en-US"]
                request.usesLanguageCorrection = false
                try VNImageRequestHandler(cgImage: crop).perform([request])
                let lines = (request.results ?? []).filter { ($0.topCandidates(1).first?.confidence ?? 0) >= 0.6 }
                    .sorted { $0.boundingBox.midY > $1.boundingBox.midY }
                texts.append(lines.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " "))
            }
            let data = try JSONSerialization.data(withJSONObject: ["type": "ocr", "texts": texts])
            FileHandle.standardError.write(data + Data([10]))
        } catch {
            event("ocr_error", "OCR frame failed")
        }
    }
}

final class AudioSink: NSObject, SCStreamOutput, SCStreamDelegate {
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        event("error", "Remote Play audio stream stopped; reconnect the app and restart capture.")
        exit(1)
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, sample.isValid, CMSampleBufferDataIsReady(sample) else { return }
        guard let description = CMSampleBufferGetFormatDescription(sample) else {
            event("error", "Invalid audio format"); exit(1)
        }
        let format = AVAudioFormat(cmAudioFormatDescription: description)
        let count = CMSampleBufferGetNumSamples(sample)
        guard count > 0 else { return }
        guard count <= 16000, format.sampleRate == 16000, format.channelCount == 1,
              format.commonFormat == .pcmFormatFloat32,
              let pcm = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(count)) else {
            event("error", "ScreenCaptureKit did not supply 16kHz mono float32 audio"); exit(1)
        }
        pcm.frameLength = AVAudioFrameCount(count)
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(sample, at: 0,
            frameCount: Int32(count), into: pcm.mutableAudioBufferList)
        guard status == noErr, let channel = pcm.floatChannelData?[0] else {
            event("error", "Audio buffer copy failed"); exit(1)
        }
        // Bounded OS pipe; Python continuously drains it. No audio or image files.
        FileHandle.standardOutput.write(Data(bytes: channel, count: count * MemoryLayout<Float>.size))
    }
}

@main struct AudioCapture {
    @MainActor static func main() async {
        _ = NSApplication.shared
        let args = Array(CommandLine.arguments.dropFirst())
        guard args.count == 1 || args.count == 3 else { event("error", "Usage: audio APP_BUNDLE_ID or --list"); exit(2) }
        guard CGPreflightScreenCaptureAccess() else {
            event("error", "Allow Screen & System Audio Recording for the launching app, then restart it."); exit(3)
        }
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
            if args[0] == "--list" {
                let apps = content.applications.map { ["name": $0.applicationName, "bundle_id": $0.bundleIdentifier] }
                let data = try JSONSerialization.data(withJSONObject: apps)
                FileHandle.standardOutput.write(data); return
            }
            let matches = content.applications.filter { $0.bundleIdentifier == args[0] }
            guard matches.count == 1, let app = matches.first, let display = content.displays.first else {
                event("error", "Selected audio app is not running or is ambiguous; open Remote Play and connect PS5."); exit(4)
            }
            // App inclusion filter is essential: never capture all system audio.
            var filter = SCContentFilter(display: display, including: [app], exceptingWindows: [])
            var selected: SCWindow? = nil
            var ocrSink: OCRSink? = nil
            if args.count == 3 {
                guard let windowID = UInt32(args[1]),
                      let window = content.windows.first(where: { $0.windowID == windowID && $0.owningApplication?.processID == app.processID }),
                      let data = args[2].data(using: .utf8),
                      let crops = try JSONSerialization.jsonObject(with: data) as? [[Double]],
                      !crops.isEmpty, crops.count <= 3,
                      crops.allSatisfy({ c in c.count == 4 && c[0] >= 0 && c[1] >= 0 && c[2] > 0 && c[3] > 0 && c[0]+c[2] <= 1 && c[1]+c[3] <= 1 }) else {
                    event("error", "Invalid Remote Play window or OCR crops"); exit(4)
                }
                selected = window
                filter = SCContentFilter(desktopIndependentWindow: window)
                ocrSink = OCRSink(crops)
            }
            let config = SCStreamConfiguration()
            config.width = 2; config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
            if let window = selected {
                config.width = min(1920, Int(window.frame.width * 2))
                config.height = max(1, Int(Double(config.width) * window.frame.height / window.frame.width))
                config.minimumFrameInterval = CMTime(value: 1, timescale: 3)
                config.queueDepth = 3
                config.ignoreShadowsSingleWindow = true
            }
            config.showsCursor = false
            config.capturesAudio = true
            config.sampleRate = 16000; config.channelCount = 1
            config.excludesCurrentProcessAudio = true
            if #available(macOS 15.0, *) { config.captureMicrophone = false }
            let sink = AudioSink()
            let stream = SCStream(filter: filter, configuration: config, delegate: sink)
            let queue = DispatchQueue(label: "ps5.audio.capture")
            try stream.addStreamOutput(sink, type: .audio, sampleHandlerQueue: queue)
            // Discard minimal video callbacks; they never cross the pipe or reach disk.
            if let ocr = ocrSink {
                try stream.addStreamOutput(ocr, type: .screen, sampleHandlerQueue: DispatchQueue(label: "ps5.ocr.capture"))
            } else {
                try stream.addStreamOutput(sink, type: .screen, sampleHandlerQueue: queue)
            }
            try await stream.startCapture()
            event("ready", "App-only 16000Hz mono float32 audio; microphone disabled")
            while NSRunningApplication(processIdentifier: app.processID)?.isTerminated == false {
                try await Task.sleep(nanoseconds: 500_000_000)
            }
            try await stream.stopCapture()
            event("error", "Audio source app closed"); exit(4)
        } catch {
            event("error", "Audio capture failed; check macOS capture permission and Remote Play connection.")
            exit(1)
        }
    }
}
