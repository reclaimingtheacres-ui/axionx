import SwiftUI
import AVFoundation
import Vision

// MARK: - Public SwiftUI entry point

struct LiveLPRScannerView: View {
    var onPlateConfirmed: (String) -> Void
    var onCancel: () -> Void

    @State private var detectedPlate: String = ""
    @State private var showConfirmation: Bool = false
    @State private var editedPlate: String = ""
    @State private var isTorchOn: Bool = false
    @State private var cameraVC: LPRCameraViewController?

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            CameraPreviewWrapper(isTorchOn: $isTorchOn, cameraVC: $cameraVC) { plate in
                guard !showConfirmation else { return }
                detectedPlate = plate
                editedPlate   = plate
                showConfirmation = true
                cameraVC?.stopCapture()
            }
            .ignoresSafeArea()

            if !showConfirmation {
                scanningOverlay
            } else {
                confirmationOverlay
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: Scanning overlay
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

    // MARK: Confirmation overlay
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
                    // Apply cooldown before allowing another scan
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

    func makeUIViewController(context: Context) -> LPRCameraViewController {
        let vc = LPRCameraViewController(onPlateDetected: onPlateDetected)
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
    private let session     = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let outputQueue = DispatchQueue(label: "com.axionx.lpr.output", qos: .userInteractive)

    // Stability: require same candidate twice in a row
    private var lastCandidate:      String = ""
    private var consecutiveCount:   Int    = 0
    private let requiredConsecutive: Int   = 2

    // Frame rate limiting
    private var lastFrameTime  = Date.distantPast
    private let frameInterval: TimeInterval = 0.6

    // Post-detection cooldown
    private var cooldownUntil = Date.distantPast
    private let cooldownSeconds: TimeInterval = 4.0

    init(onPlateDetected: @escaping (String) -> Void) {
        self.onPlateDetected = onPlateDetected
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupSession()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        startCapture()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        stopCapture()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    private func setupSession() {
        session.sessionPreset = .hd1280x720
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input  = try? AVCaptureDeviceInput(device: device) else { return }
        if session.canAddInput(input) { session.addInput(input) }

        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: outputQueue)
        output.alwaysDiscardsLateVideoFrames = true
        if session.canAddOutput(output) { session.addOutput(output) }

        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        view.layer.insertSublayer(layer, at: 0)
        previewLayer = layer
    }

    func startCapture() {
        guard !session.isRunning else { return }
        outputQueue.async { self.session.startRunning() }
    }

    func stopCapture() {
        guard session.isRunning else { return }
        outputQueue.async { self.session.stopRunning() }
    }

    /// Apply a post-submission cooldown and reset the stability counter.
    func applyCooldown() {
        cooldownUntil = Date().addingTimeInterval(cooldownSeconds)
        lastCandidate    = ""
        consecutiveCount = 0
    }

    /// Reset stability state and restart capture for a deliberate rescan.
    func resetAndResume() {
        lastCandidate    = ""
        consecutiveCount = 0
        cooldownUntil    = Date.distantPast
        startCapture()
    }

    func setTorch(_ on: Bool) {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else { return }
        try? device.lockForConfiguration()
        device.torchMode = on ? .on : .off
        device.unlockForConfiguration()
    }

    // MARK: Sample buffer delegate
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        let now = Date()

        // Respect cooldown
        guard now >= cooldownUntil else { return }
        // Respect frame rate limit
        guard now.timeIntervalSince(lastFrameTime) >= frameInterval else { return }
        lastFrameTime = now

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        let request = VNRecognizeTextRequest { [weak self] req, _ in
            guard let self = self else { return }
            let observations = req.results as? [VNRecognizedTextObservation] ?? []

            // Centre-of-frame preference: filter observations whose midX is within the centre third
            let centred = observations.filter { obs in
                let midX = (obs.boundingBox.minX + obs.boundingBox.maxX) / 2
                return midX >= 0.2 && midX <= 0.8
            }
            let source = centred.isEmpty ? observations : centred

            guard let plate = PlateCandidateExtractor.bestCandidate(from: source) else {
                // Different or no candidate — reset streak
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

            // Only fire when the same candidate has been seen consecutively enough times
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
        try? handler.perform([request])
    }
}
