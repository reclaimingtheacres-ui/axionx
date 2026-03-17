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
        let statusStr = statusString(status)
        print("[CameraPermission] ensureCameraPermission called, status: \(statusStr) (\(status.rawValue))")
        pushStatusToJS(statusStr)

        if status == .notDetermined {
            print("[CameraPermission] Requesting camera access proactively")
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                let result = granted ? "authorized" : "denied"
                print("[CameraPermission] Proactive permission result: \(result)")
                DispatchQueue.main.async {
                    self?.pushStatusToJS(result)
                }
            }
        }
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else {
            print("[CameraPermission] Failed to parse message body: \(message.body)")
            return
        }

        print("[CameraPermission] Received action: \(action)")

        switch action {
        case "check":
            let status = currentStatusString()
            print("[CameraPermission] check → \(status)")
            pushStatusToJS(status)

        case "request":
            let current = AVCaptureDevice.authorizationStatus(for: .video)
            print("[CameraPermission] request — current status: \(statusString(current)) (\(current.rawValue))")
            if current == .notDetermined {
                print("[CameraPermission] Calling AVCaptureDevice.requestAccess(for: .video)")
                AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                    let result = granted ? "authorized" : "denied"
                    print("[CameraPermission] requestAccess result: \(result)")
                    DispatchQueue.main.async {
                        self?.pushStatusToJS(result)
                    }
                }
            } else {
                let status = currentStatusString()
                print("[CameraPermission] Already determined: \(status)")
                pushStatusToJS(status)
            }

        default:
            print("[CameraPermission] Unknown action: \(action)")
        }
    }

    private func currentStatusString() -> String {
        return statusString(AVCaptureDevice.authorizationStatus(for: .video))
    }

    private func statusString(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:    return "authorized"
        case .denied:        return "denied"
        case .restricted:    return "restricted"
        case .notDetermined: return "not_determined"
        @unknown default:    return "unknown"
        }
    }

    private func pushStatusToJS(_ status: String) {
        let js = "window._axCameraStatus='\(status)';if(window._cameraPermissionResult){window._cameraPermissionResult('\(status)');}"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js) { _, error in
                if let error = error {
                    print("[CameraPermission] JS eval error: \(error.localizedDescription)")
                }
            }
        }
    }
}
