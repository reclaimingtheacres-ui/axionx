import Foundation
import AVFoundation
import WebKit

final class CameraPermissionService: NSObject, WKScriptMessageHandler {

    static let shared = CameraPermissionService()
    private override init() { super.init() }

    private weak var webView: WKWebView?

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func ensureCameraPermission() {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        print("[CameraPermission] ensureCameraPermission called, status: \(status.rawValue)")
        if status == .notDetermined {
            print("[CameraPermission] Requesting camera access proactively")
            AVCaptureDevice.requestAccess(for: .video) { granted in
                print("[CameraPermission] Proactive permission result: \(granted)")
            }
        }
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }

        switch action {
        case "check":
            let status = currentStatusString()
            print("[CameraPermission] check → \(status)")
            sendToJS(status)

        case "request":
            let current = AVCaptureDevice.authorizationStatus(for: .video)
            if current == .notDetermined {
                print("[CameraPermission] Requesting camera access")
                AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                    let result = granted ? "authorized" : "denied"
                    print("[CameraPermission] Request result: \(result)")
                    DispatchQueue.main.async {
                        self?.sendToJS(result)
                    }
                }
            } else {
                let status = currentStatusString()
                print("[CameraPermission] Already determined: \(status)")
                sendToJS(status)
            }

        default:
            print("[CameraPermission] Unknown action: \(action)")
        }
    }

    private func currentStatusString() -> String {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:    return "authorized"
        case .denied:        return "denied"
        case .restricted:    return "restricted"
        case .notDetermined: return "not_determined"
        @unknown default:    return "unknown"
        }
    }

    private func sendToJS(_ status: String) {
        let js = "if(window._cameraPermissionResult){window._cameraPermissionResult('\(status)');}"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js) { _, error in
                if let error = error {
                    print("[CameraPermission] JS eval error: \(error.localizedDescription)")
                }
            }
        }
    }
}
