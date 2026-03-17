import Foundation
import AVFoundation
import Vision
import WebKit

@MainActor
final class PatrolCameraService: NSObject, WKScriptMessageHandler {

    static let shared = PatrolCameraService()
    private override init() { super.init() }

    private weak var webView: WKWebView?
    private var session: AVCaptureSession?
    private let outputQueue = DispatchQueue(label: "com.axionx.patrol.camera", qos: .userInteractive)
    private var isRunning = false

    private var lastFrameTime = Date.distantPast
    private let frameInterval: TimeInterval = 0.6

    private var lastCandidate = ""
    private var consecutiveCount = 0
    private let requiredConsecutive = 2

    private var cooldownPlates: [String: Date] = [:]
    private let cooldownSeconds: TimeInterval = 30.0

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }

        switch action {
        case "start":
            startPatrol()
        case "stop":
            stopPatrol()
        case "torch":
            let on = body["on"] as? Bool ?? false
            setTorch(on)
        default:
            break
        }
    }

    private func startPatrol() {
        guard !isRunning else { return }

        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupAndStart()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    if granted {
                        self?.setupAndStart()
                    } else {
                        self?.sendStatus("permission_denied")
                    }
                }
            }
        case .denied:
            sendStatus("permission_denied")
        case .restricted:
            sendStatus("restricted")
        @unknown default:
            sendStatus("error")
        }
    }

    private func setupAndStart() {
        let captureSession = AVCaptureSession()
        captureSession.beginConfiguration()
        captureSession.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            captureSession.commitConfiguration()
            sendStatus("no_camera")
            return
        }

        guard let input = try? AVCaptureDeviceInput(device: device),
              captureSession.canAddInput(input) else {
            captureSession.commitConfiguration()
            sendStatus("setup_failed")
            return
        }
        captureSession.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: outputQueue)
        output.alwaysDiscardsLateVideoFrames = true

        guard captureSession.canAddOutput(output) else {
            captureSession.commitConfiguration()
            sendStatus("setup_failed")
            return
        }
        captureSession.addOutput(output)
        captureSession.commitConfiguration()

        self.session = captureSession
        isRunning = true
        cooldownPlates.removeAll()
        lastCandidate = ""
        consecutiveCount = 0

        outputQueue.async { [weak self] in
            self?.session?.startRunning()
        }

        sendStatus("active")
    }

    func stopPatrol() {
        guard isRunning else { return }
        isRunning = false
        outputQueue.async { [weak self] in
            self?.session?.stopRunning()
        }
        session = nil
        lastCandidate = ""
        consecutiveCount = 0
    }

    private func setTorch(_ on: Bool) {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else { return }
        do {
            try device.lockForConfiguration()
            device.torchMode = on ? .on : .off
            device.unlockForConfiguration()
        } catch {}
    }

    private func sendStatus(_ status: String) {
        let js = "if(window._nativePatrolStatus) window._nativePatrolStatus('\(status)');"
        webView?.evaluateJavaScript(js, completionHandler: nil)
    }

    private func sendPlate(_ plate: String) {
        let safe = plate.replacingOccurrences(of: "'", with: "\\'")
        let js = "if(window._nativePatrolPlateDetected) window._nativePatrolPlateDetected('\(safe)');"
        webView?.evaluateJavaScript(js, completionHandler: nil)
    }
}

extension PatrolCameraService: AVCaptureVideoDataOutputSampleBufferDelegate {

    nonisolated func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        let now = Date()
        guard now.timeIntervalSince(lastFrameTime) >= frameInterval else { return }
        lastFrameTime = now

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        let request = VNRecognizeTextRequest { [weak self] req, error in
            guard let self = self else { return }
            if error != nil { return }

            let observations = req.results as? [VNRecognizedTextObservation] ?? []

            let centred = observations.filter { obs in
                let midX = (obs.boundingBox.minX + obs.boundingBox.maxX) / 2
                return midX >= 0.15 && midX <= 0.85
            }
            let source = centred.isEmpty ? observations : centred

            guard let plate = PlateCandidateExtractor.bestCandidate(from: source) else {
                self.lastCandidate = ""
                self.consecutiveCount = 0
                return
            }

            if plate == self.lastCandidate {
                self.consecutiveCount += 1
            } else {
                self.lastCandidate = plate
                self.consecutiveCount = 1
            }

            guard self.consecutiveCount >= self.requiredConsecutive else { return }
            self.lastCandidate = ""
            self.consecutiveCount = 0

            let cooldownEnd = self.cooldownPlates[plate]
            if let end = cooldownEnd, now < end { return }
            self.cooldownPlates[plate] = now.addingTimeInterval(self.cooldownSeconds)

            DispatchQueue.main.async {
                self.sendPlate(plate)
            }
        }
        request.recognitionLevel = .fast
        request.usesLanguageCorrection = false
        request.minimumTextHeight = 0.04

        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .right)
        do {
            try handler.perform([request])
        } catch {}
    }
}
