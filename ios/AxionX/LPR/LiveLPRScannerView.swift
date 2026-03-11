import SwiftUI
import AVFoundation
import Vision

enum CameraError: Equatable {
    case permissionDenied
    case restricted
    case unavailable
    case setupFailed(String)
}

struct LiveLPRScannerView: View {
    var onPlateConfirmed: (String) -> Void
    var onCancel: () -> Void

    @State private var detectedPlate: String = ""
    @State private var showConfirmation: Bool = false
    @State private var editedPlate: String = ""
    @State private var isTorchOn: Bool = false
    @State private var cameraVC: LPRCameraViewController?
    @State private var cameraError: CameraError?

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if cameraError == nil {
                CameraPreviewWrapper(
                    isTorchOn: $isTorchOn,
                    cameraVC: $cameraVC,
                    onPlateDetected: { plate in
                        guard !showConfirmation else { return }
                        detectedPlate = plate
                        editedPlate   = plate
                        showConfirmation = true
                        cameraVC?.stopCapture()
                    },
                    onCameraError: { error in
                        cameraError = error
                    }
                )
                .ignoresSafeArea()
            }

            if let error = cameraError {
                cameraErrorOverlay(error)
            } else if !showConfirmation {
                scanningOverlay
            } else {
                confirmationOverlay
            }
        }
        .preferredColorScheme(.dark)
    }

    private func cameraErrorOverlay(_ error: CameraError) -> some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 20) {
                Image(systemName: errorIcon(error))
                    .font(.system(size: 44, weight: .light))
                    .foregroundColor(Color(red: 0.97, green: 0.38, blue: 0.38))

                Text(errorTitle(error))
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)

                Text(errorMessage(error))
                    .font(.system(size: 14))
                    .foregroundColor(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                if error == .permissionDenied {
                    Button(action: {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }) {
                        HStack(spacing: 8) {
                            Image(systemName: "gear")
                            Text("Open Settings")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.white.opacity(0.15))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                }

                if error != .permissionDenied && error != .restricted {
                    Button(action: {
                        cameraError = nil
                        cameraVC?.retrySetup()
                    }) {
                        HStack(spacing: 8) {
                            Image(systemName: "arrow.clockwise")
                            Text("Retry")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color(red: 0.15, green: 0.5, blue: 0.95))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                }

                Button(action: { onCancel() }) {
                    HStack(spacing: 8) {
                        Image(systemName: "keyboard")
                        Text("Manual Plate Entry")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.white.opacity(0.15))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }

                Button("Cancel") { onCancel() }
                    .font(.system(size: 15))
                    .foregroundColor(.white.opacity(0.6))
                    .padding(.top, 4)
            }
            .padding(24)
            .background(Color(white: 0.1))
            .cornerRadius(24)
            .padding(.horizontal, 20)
            .padding(.bottom, 40)
        }
    }

    private func errorIcon(_ error: CameraError) -> String {
        switch error {
        case .permissionDenied: return "camera.fill"
        case .restricted:       return "lock.fill"
        case .unavailable:      return "camera.metering.unknown"
        case .setupFailed:      return "exclamationmark.triangle.fill"
        }
    }

    private func errorTitle(_ error: CameraError) -> String {
        switch error {
        case .permissionDenied: return "Camera Access Blocked"
        case .restricted:       return "Camera Restricted"
        case .unavailable:      return "Camera Unavailable"
        case .setupFailed:      return "Camera Error"
        }
    }

    private func errorMessage(_ error: CameraError) -> String {
        switch error {
        case .permissionDenied:
            return "Camera access is turned off for AxionX. Enable Camera in iPhone Settings → AxionX → Camera."
        case .restricted:
            return "Camera access is restricted on this device. Contact your administrator or check device management settings."
        case .unavailable:
            return "No camera was found on this device. Use Manual Plate Entry instead."
        case .setupFailed(let detail):
            return "The camera failed to start: \(detail). Close this screen and try again. Another app may be using the camera."
        }
    }

    private var scanningOverlay: some View {
        VStack(spacing: 0) {
            HStack {
                Spacer()
                Text("Align registration plate in frame")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.white)
                    .padding(.vertical, 10)
                    .padding(.horizontal, 16)
                    .background(Color.black.opacity(0.55))
                    .cornerRadius(10)
                Spacer()
            }
            .padding(.top, 56)

            Spacer()
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.white.opacity(0.75), lineWidth: 2)
                .frame(width: 280, height: 90)
            Spacer()

            HStack(spacing: 0) {
                Button(action: { onCancel() }) {
                    controlLabel(icon: "xmark", label: "Cancel")
                }
                Spacer()
                Button(action: {
                    isTorchOn.toggle()
                    cameraVC?.setTorch(isTorchOn)
                }) {
                    controlLabel(icon: isTorchOn ? "bolt.fill" : "bolt.slash", label: "Torch")
                }
                Spacer()
                Button(action: { onCancel() }) {
                    controlLabel(icon: "keyboard", label: "Manual")
                }
            }
            .padding(.horizontal, 40)
            .padding(.bottom, 44)
            .background(Color.black.opacity(0.6))
        }
    }

    private var confirmationOverlay: some View {
        VStack(spacing: 0) {
            Spacer()
            VStack(spacing: 20) {
                Text("Plate Detected")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)
                    .tracking(1)

                TextField("Registration", text: $editedPlate)
                    .font(.system(size: 36, weight: .black, design: .monospaced))
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .autocapitalization(.allCharacters)
                    .autocorrectionDisabled()
                    .padding(.vertical, 14)
                    .padding(.horizontal, 12)
                    .background(Color.white.opacity(0.15))
                    .cornerRadius(12)
                    .onChange(of: editedPlate) { val in
                        editedPlate = PlateCandidateExtractor.normalisePlate(val)
                    }

                Text("Tap to correct if needed")
                    .font(.system(size: 13))
                    .foregroundColor(.white.opacity(0.55))

                Button(action: {
                    let plate = PlateCandidateExtractor.normalisePlate(editedPlate)
                    guard !plate.isEmpty else { return }
                    cameraVC?.applyCooldown()
                    onPlateConfirmed(plate)
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "magnifyingglass")
                        Text("Search Active Assets")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
                    .background(Color(red: 0.15, green: 0.5, blue: 0.95))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }

                Button(action: {
                    showConfirmation = false
                    detectedPlate = ""
                    editedPlate   = ""
                    cameraVC?.resetAndResume()
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "camera.viewfinder")
                        Text("Rescan")
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .background(Color.white.opacity(0.15))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }

                Button("Cancel") { onCancel() }
                    .font(.system(size: 15))
                    .foregroundColor(.white.opacity(0.6))
                    .padding(.top, 4)
            }
            .padding(24)
            .background(Color(white: 0.1))
            .cornerRadius(24)
            .padding(.horizontal, 20)
            .padding(.bottom, 40)
        }
    }

    private func controlLabel(icon: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 22))
            Text(label)
                .font(.system(size: 11, weight: .medium))
        }
        .foregroundColor(.white)
        .frame(width: 64)
        .padding(.vertical, 14)
    }
}

// MARK: - UIViewControllerRepresentable wrapper

private struct CameraPreviewWrapper: UIViewControllerRepresentable {
    @Binding var isTorchOn: Bool
    @Binding var cameraVC: LPRCameraViewController?
    var onPlateDetected: (String) -> Void
    var onCameraError: (CameraError) -> Void

    func makeUIViewController(context: Context) -> LPRCameraViewController {
        let vc = LPRCameraViewController(
            onPlateDetected: onPlateDetected,
            onCameraError: onCameraError
        )
        DispatchQueue.main.async { cameraVC = vc }
        return vc
    }

    func updateUIViewController(_ uiViewController: LPRCameraViewController, context: Context) {
        uiViewController.setTorch(isTorchOn)
    }
}

// MARK: - Camera view controller with Vision text recognition

final class LPRCameraViewController: UIViewController, AVCaptureVideoDataOutputSampleBufferDelegate {

    var onPlateDetected: (String) -> Void
    var onCameraError: (CameraError) -> Void
    private var session: AVCaptureSession?
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let outputQueue = DispatchQueue(label: "com.axionx.lpr.output", qos: .userInteractive)
    private var isSessionConfigured = false

    private var lastCandidate:      String = ""
    private var consecutiveCount:   Int    = 0
    private let requiredConsecutive: Int   = 2

    private var lastFrameTime  = Date.distantPast
    private let frameInterval: TimeInterval = 0.6

    private var cooldownUntil = Date.distantPast
    private let cooldownSeconds: TimeInterval = 4.0

    init(onPlateDetected: @escaping (String) -> Void,
         onCameraError: @escaping (CameraError) -> Void) {
        self.onPlateDetected = onPlateDetected
        self.onCameraError = onCameraError
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        checkAuthorizationAndSetup()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        if isSessionConfigured {
            startCapture()
        }
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        stopCapture()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    private func checkAuthorizationAndSetup() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupSession()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    if granted {
                        self?.setupSession()
                    } else {
                        self?.onCameraError(.permissionDenied)
                    }
                }
            }
        case .denied:
            onCameraError(.permissionDenied)
        case .restricted:
            onCameraError(.restricted)
        @unknown default:
            onCameraError(.setupFailed("Unknown authorization status"))
        }
    }

    private func setupSession() {
        let captureSession = AVCaptureSession()

        captureSession.beginConfiguration()
        captureSession.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            captureSession.commitConfiguration()
            DispatchQueue.main.async { [weak self] in
                self?.onCameraError(.unavailable)
            }
            return
        }

        let input: AVCaptureDeviceInput
        do {
            input = try AVCaptureDeviceInput(device: device)
        } catch {
            captureSession.commitConfiguration()
            DispatchQueue.main.async { [weak self] in
                self?.onCameraError(.setupFailed(error.localizedDescription))
            }
            return
        }

        guard captureSession.canAddInput(input) else {
            captureSession.commitConfiguration()
            DispatchQueue.main.async { [weak self] in
                self?.onCameraError(.setupFailed("Cannot add camera input"))
            }
            return
        }
        captureSession.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: outputQueue)
        output.alwaysDiscardsLateVideoFrames = true

        guard captureSession.canAddOutput(output) else {
            captureSession.commitConfiguration()
            DispatchQueue.main.async { [weak self] in
                self?.onCameraError(.setupFailed("Cannot add video output"))
            }
            return
        }
        captureSession.addOutput(output)
        captureSession.commitConfiguration()

        self.session = captureSession
        isSessionConfigured = true

        let layer = AVCaptureVideoPreviewLayer(session: captureSession)
        layer.videoGravity = .resizeAspectFill
        view.layer.insertSublayer(layer, at: 0)
        previewLayer = layer
        layer.frame = view.bounds

        startCapture()
    }

    func retrySetup() {
        previewLayer?.removeFromSuperlayer()
        previewLayer = nil
        session = nil
        isSessionConfigured = false
        lastCandidate    = ""
        consecutiveCount = 0
        checkAuthorizationAndSetup()
    }

    func startCapture() {
        guard let session = session, !session.isRunning else { return }
        outputQueue.async { [weak self] in
            self?.session?.startRunning()
        }
    }

    func stopCapture() {
        guard let session = session, session.isRunning else { return }
        outputQueue.async { [weak self] in
            self?.session?.stopRunning()
        }
    }

    func applyCooldown() {
        cooldownUntil = Date().addingTimeInterval(cooldownSeconds)
        lastCandidate    = ""
        consecutiveCount = 0
    }

    func resetAndResume() {
        lastCandidate    = ""
        consecutiveCount = 0
        cooldownUntil    = Date.distantPast
        startCapture()
    }

    func setTorch(_ on: Bool) {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else { return }
        do {
            try device.lockForConfiguration()
            device.torchMode = on ? .on : .off
            device.unlockForConfiguration()
        } catch {
            // Torch toggle failed — non-critical, continue
        }
    }

    // MARK: Sample buffer delegate
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        let now = Date()

        guard now >= cooldownUntil else { return }
        guard now.timeIntervalSince(lastFrameTime) >= frameInterval else { return }
        lastFrameTime = now

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        let request = VNRecognizeTextRequest { [weak self] req, error in
            guard let self = self else { return }
            if error != nil { return }

            let observations = req.results as? [VNRecognizedTextObservation] ?? []

            let centred = observations.filter { obs in
                let midX = (obs.boundingBox.minX + obs.boundingBox.maxX) / 2
                return midX >= 0.2 && midX <= 0.8
            }
            let source = centred.isEmpty ? observations : centred

            guard let plate = PlateCandidateExtractor.bestCandidate(from: source) else {
                self.lastCandidate    = ""
                self.consecutiveCount = 0
                return
            }

            if plate == self.lastCandidate {
                self.consecutiveCount += 1
            } else {
                self.lastCandidate    = plate
                self.consecutiveCount = 1
            }

            guard self.consecutiveCount >= self.requiredConsecutive else { return }
            self.lastCandidate    = ""
            self.consecutiveCount = 0

            DispatchQueue.main.async {
                self.onPlateDetected(plate)
            }
        }
        request.recognitionLevel      = .fast
        request.usesLanguageCorrection = false
        request.minimumTextHeight      = 0.05

        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .right)
        do {
            try handler.perform([request])
        } catch {
            // Vision request failed on this frame — non-critical, continue to next
        }
    }
}

#Preview {
    LiveLPRScannerView(onPlateConfirmed: { _ in }, onCancel: {})
}
