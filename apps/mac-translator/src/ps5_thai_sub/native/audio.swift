import AppKit
import ScreenCaptureKit
import AVFoundation
import CoreMedia

func event(_ type: String, _ message: String) {
    let data = try! JSONSerialization.data(withJSONObject: ["type": type, "message": message])
    FileHandle.standardError.write(data + Data([10]))
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
        guard args.count == 1 else { event("error", "Usage: audio APP_BUNDLE_ID or --list"); exit(2) }
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
            let filter = SCContentFilter(display: display, including: [app], exceptingWindows: [])
            let config = SCStreamConfiguration()
            config.width = 2; config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
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
            try stream.addStreamOutput(sink, type: .screen, sampleHandlerQueue: queue)
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
