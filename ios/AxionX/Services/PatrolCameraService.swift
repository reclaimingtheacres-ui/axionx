import Foundation
import AVFoundation
import Vision
import WebKit

final class PatrolCameraService: NSObject, WKScriptMessageHandler {

    static let shared = PatrolCameraService()
    private override init() { super.init() }

    private weak var webView: WKWebView?
    private var session: AVCaptureSession?
    private let outputQueue = DispatchQueue(label: "com.axionx.patrol.camera", qos: .userInteractive)
    private var isRunning = false
    private var permissionRequested = false

    private let stateLock = NSLock()
    private var _lastFrameTime = Date.distantPast
    private var _lastCandidate = ""
    private var _consecutiveCount = 0
    private let requiredConsecutive = 2
    private var _cooldownPlates: [String: Date] = [:]
    private let cooldownSeconds: TimeInterval = 30.0
    private let frameInterval: TimeInterval = 0.6

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func ensureCameraPermission() {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        print("[PatrolCamera] ensureCameraPermission called, status: \(status.rawValue)")
        if status == .notDetermined && !permissionRequested {
            permissionRequested = true
            print("[PatrolCamera] Requesting camera access proactively")
            AVCaptureDevice.requestAccess(for: .video) { granted in
                print("[PatrolCamera] Proactive permission result: \(granted)")
            }
        }
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        print("[PatrolCamera] Received message: \(message.body)")
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else {
            print("[PatrolCamera] Failed to parse message body")
            return
        }

        switch action {
        case "requestPermission":
            handlePermissionRequest()
        case "start":
            startPatrol()
        case "stop":
            stopPatrol()
        case "torch":
            let on = body["on"] as? Bool ?? false
            setTorch(on)
        default:
            print("[PatrolCamera] Unknown action: \(action)")
            break
        }
    }

    private func handlePermissionRequest() {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        print("[PatrolCamera] handlePermissionRequest, status: \(status.rawValue)")
        switch status {
        case .authorized:
            sendStatus("permission_granted")
        case .notDetermined:
            sendStatus("not_determined")
            permissionRequested = true
            print("[PatrolCamera] Calling AVCaptureDevice.requestAccess(for: .video)")
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                print("[PatrolCamera] requestAccess result: \(granted)")
                DispatchQueue.main.async {
                    self?.sendStatus(granted ? "permission_granted" : "permission_denied")
                }
            }
        case .denied:
            sendStatus("permission_denied")
        case .restricted:
            sendStatus("permission_denied")
        @unknown default:
            sendStatus("error")
        }
    }

    private func startPatrol() {
        print("[PatrolCamera] startPatrol called, isRunning: \(isRunning)")
        guard !isRunning else { return }

        let status = AVCaptureDevice.authorizationStatus(for: .video)
        print("[PatrolCamera] Camera auth status: \(status.rawValue) (0=notDetermined, 1=restricted, 2=denied, 3=authorized)")

        switch status {
        case .authorized:
            print("[PatrolCamera] Authorized — setting up camera")
            setupAndStart()
        case .notDetermined:
            print("[PatrolCamera] Not determined — requesting access")
            sendStatus("not_determined")
            permissionRequested = true
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                print("[PatrolCamera] requestAccess callback: granted=\(granted)")
                DispatchQueue.main.async {
                    if granted {
                        self?.setupAndStart()
                    } else {
                        self?.sendStatus("permission_denied")
                    }
                }
            }
        case .denied:
            print("[PatrolCamera] Denied")
            sendStatus("permission_denied")
        case .restricted:
            print("[PatrolCamera] Restricted")
            sendStatus("permission_denied")
        @unknown default:
            print("[PatrolCamera] Unknown status")
            sendStatus("error")
        }
    }

    private func setupAndStart() {
        print("[PatrolCamera] setupAndStart")
        let captureSession = AVCaptureSession()
        captureSession.beginConfiguration()
        captureSession.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            captureSession.commitConfiguration()
            print("[PatrolCamera] No camera device found")
            sendStatus("no_camera")
            return
        }

        guard let input = try? AVCaptureDeviceInput(device: device),
              captureSession.canAddInput(input) else {
            captureSession.commitConfiguration()
            print("[PatrolCamera] Failed to create camera input")
            sendStatus("setup_failed")
            return
        }
        captureSession.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: outputQueue)
        output.alwaysDiscardsLateVideoFrames = true

        guard captureSession.canAddOutput(output) else {
            captureSession.commitConfiguration()
            print("[PatrolCamera] Failed to add video output")
            sendStatus("setup_failed")
            return
        }
        captureSession.addOutput(output)
        captureSession.commitConfiguration()

        self.session = captureSession
        isRunning = true

        stateLock.lock()
        _cooldownPlates.removeAll()
        _lastCandidate = ""
        _consecutiveCount = 0
        _lastFrameTime = Date.distantPast
        stateLock.unlock()

        outputQueue.async { [weak self] in
            print("[PatrolCamera] Starting capture session on outputQueue")
            self?.session?.startRunning()
            print("[PatrolCamera] Capture session running")
        }

        sendStatus("active")
        print("[PatrolCamera] Sent 'active' status")
    }

    func stopPatrol() {
        guard isRunning else { return }
        print("[PatrolCamera] Stopping patrol")
        isRunning = false
        outputQueue.async { [weak self] in
            self?.session?.stopRunning()
        }
        session = nil

        stateLock.lock()
        _lastCandidate = ""
        _consecutiveCount = 0
        stateLock.unlock()
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
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js, completionHandler: nil)
        }
    }

    private func sendPlate(_ plate: String) {
        let safe = plate.replacingOccurrences(of: "'", with: "\\'")
        let js = "if(window._nativePatrolPlateDetected) window._nativePatrolPlateDetected('\(safe)');"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js, completionHandler: nil)
        }
    }
}

extension PatrolCameraService: AVCaptureVideoDataOutputSampleBufferDelegate {

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        let now = Date()

        stateLock.lock()
        let lastFrame = _lastFrameTime
        stateLock.unlock()

        guard now.timeIntervalSince(lastFrame) >= frameInterval else { return }

        stateLock.lock()
        _lastFrameTime = now
        stateLock.unlock()

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
                self.stateLock.lock()
                self._lastCandidate = ""
                self._consecutiveCount = 0
                self.stateLock.unlock()
                return
            }

            self.stateLock.lock()
            if plate == self._lastCandidate {
                self._consecutiveCount += 1
            } else {
                self._lastCandidate = plate
                self._consecutiveCount = 1
            }
            let count = self._consecutiveCount
            self.stateLock.unlock()

            guard count >= self.requiredConsecutive else { return }

            self.stateLock.lock()
            self._lastCandidate = ""
            self._consecutiveCount = 0
            let cooldownEnd = self._cooldownPlates[plate]
            if let end = cooldownEnd, now < end {
                self.stateLock.unlock()
                return
            }
            self._cooldownPlates[plate] = now.addingTimeInterval(self.cooldownSeconds)
            self.stateLock.unlock()

            self.sendPlate(plate)
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
