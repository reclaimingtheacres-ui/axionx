import UIKit
import AVFoundation
import WebKit

final class CameraCaptureService: NSObject, WKScriptMessageHandler {

    static let shared = CameraCaptureService()
    private override init() { super.init() }

    private weak var webView: WKWebView?
    private var callbackId: String?

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else {
            print("[CameraCapture] Failed to parse message body: \(message.body)")
            return
        }

        print("[CameraCapture] Received action: \(action)")

        switch action {
        case "capture":
            callbackId = body["callbackId"] as? String
            openCamera()
        default:
            print("[CameraCapture] Unknown action: \(action)")
        }
    }

    private func openCamera() {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            print("[CameraCapture] Camera not available")
            sendResult(nil, error: "Camera not available on this device")
            return
        }

        let status = AVCaptureDevice.authorizationStatus(for: .video)
        guard status == .authorized else {
            print("[CameraCapture] Camera not authorized: \(status.rawValue)")
            sendResult(nil, error: "Camera permission not granted")
            return
        }

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            let picker = UIImagePickerController()
            picker.sourceType = .camera
            picker.cameraDevice = .rear
            picker.mediaTypes = ["public.image"]
            picker.allowsEditing = false
            picker.delegate = self

            guard let vc = self.topViewController() else {
                print("[CameraCapture] No view controller to present camera")
                self.sendResult(nil, error: "Unable to present camera")
                return
            }

            print("[CameraCapture] Presenting camera picker")
            vc.present(picker, animated: true)
        }
    }

    private func sendResult(_ base64: String?, error: String?) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self, let wv = self.webView else { return }
            let cbId = self.callbackId ?? ""

            if let b64 = base64 {
                let js = "if(window._cameraCaptureCallback){window._cameraCaptureCallback('\(cbId)','\(b64)',null);}"
                wv.evaluateJavaScript(js) { _, err in
                    if let err = err {
                        print("[CameraCapture] JS callback error: \(err.localizedDescription)")
                    }
                }
            } else {
                let errMsg = (error ?? "Unknown error").replacingOccurrences(of: "'", with: "\\'")
                let js = "if(window._cameraCaptureCallback){window._cameraCaptureCallback('\(cbId)',null,'\(errMsg)');}"
                wv.evaluateJavaScript(js) { _, err in
                    if let err = err {
                        print("[CameraCapture] JS callback error: \(err.localizedDescription)")
                    }
                }
            }
        }
    }

    private func topViewController() -> UIViewController? {
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = scene.keyWindow else { return nil }
        var vc = window.rootViewController
        while let presented = vc?.presentedViewController { vc = presented }
        return vc
    }
}

extension CameraCaptureService: UIImagePickerControllerDelegate, UINavigationControllerDelegate {

    func imagePickerController(
        _ picker: UIImagePickerController,
        didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]
    ) {
        print("[CameraCapture] didFinishPickingMediaWithInfo called")

        picker.dismiss(animated: true) { [weak self] in
            guard let self = self else { return }

            guard let image = info[.originalImage] as? UIImage else {
                print("[CameraCapture] No image in picker result")
                self.sendResult(nil, error: "No image captured")
                return
            }

            print("[CameraCapture] Got image: \(image.size.width)x\(image.size.height)")

            let resized = self.resizeIfNeeded(image, maxDimension: 1920)
            guard let jpegData = resized.jpegData(compressionQuality: 0.82) else {
                print("[CameraCapture] JPEG compression failed")
                self.sendResult(nil, error: "Image compression failed")
                return
            }

            print("[CameraCapture] Compressed to \(jpegData.count) bytes")
            let base64 = jpegData.base64EncodedString()
            print("[CameraCapture] Base64 length: \(base64.count)")
            self.sendResult(base64, error: nil)
        }
    }

    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
        print("[CameraCapture] User cancelled")
        picker.dismiss(animated: true) { [weak self] in
            self?.sendResult(nil, error: "cancelled")
        }
    }

    private func resizeIfNeeded(_ image: UIImage, maxDimension: CGFloat) -> UIImage {
        let w = image.size.width
        let h = image.size.height
        guard w > maxDimension || h > maxDimension else { return image }

        let ratio = min(maxDimension / w, maxDimension / h)
        let newSize = CGSize(width: round(w * ratio), height: round(h * ratio))

        UIGraphicsBeginImageContextWithOptions(newSize, true, 1.0)
        image.draw(in: CGRect(origin: .zero, size: newSize))
        let resized = UIGraphicsGetImageFromCurrentImageContext() ?? image
        UIGraphicsEndImageContext()
        return resized
    }
}
