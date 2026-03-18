import UIKit
import AVFoundation
import WebKit

final class CameraCaptureService: NSObject, WKScriptMessageHandler {

    static let shared = CameraCaptureService()
    private override init() { super.init() }

    private weak var webView: WKWebView?
    private var callbackId: String?
    private var activePicker: UIImagePickerController?

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
            let useRear = (body["camera"] as? String) != "front"
            openCamera(rearCamera: useRear)
        default:
            print("[CameraCapture] Unknown action: \(action)")
        }
    }

    private func openCamera(rearCamera: Bool = true) {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            print("[CameraCapture] Camera source not available")
            sendResult(nil, error: "Camera not available on this device")
            return
        }

        let status = AVCaptureDevice.authorizationStatus(for: .video)
        if status == .notDetermined {
            print("[CameraCapture] Camera permission not determined, requesting")
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                if granted {
                    DispatchQueue.main.async { self?.presentPicker(rearCamera: rearCamera) }
                } else {
                    self?.sendResult(nil, error: "Camera permission denied")
                }
            }
            return
        }

        guard status == .authorized else {
            print("[CameraCapture] Camera not authorized: \(status.rawValue)")
            sendResult(nil, error: "Camera permission not granted")
            return
        }

        DispatchQueue.main.async { [weak self] in
            self?.presentPicker(rearCamera: rearCamera)
        }
    }

    private func presentPicker(rearCamera: Bool) {
        guard activePicker == nil else {
            print("[CameraCapture] Picker already active, ignoring")
            return
        }

        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.cameraDevice = rearCamera ? .rear : .front
        picker.cameraCaptureMode = .photo
        picker.mediaTypes = ["public.image"]
        picker.allowsEditing = false
        picker.modalPresentationStyle = .overFullScreen
        picker.isModalInPresentation = true
        picker.delegate = self

        activePicker = picker

        guard let vc = topViewController() else {
            print("[CameraCapture] No view controller to present camera")
            activePicker = nil
            sendResult(nil, error: "Unable to present camera")
            return
        }

        print("[CameraCapture] Presenting camera picker on \(type(of: vc))")
        vc.present(picker, animated: true) {
            print("[CameraCapture] Camera picker presented successfully")
        }
    }

    private func sendResult(_ base64: String?, error: String?) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self, let wv = self.webView else { return }
            let cbId = self.callbackId ?? ""

            if let b64 = base64 {
                let js = "if(window._cameraCaptureCallback){window._cameraCaptureCallback('\(cbId)','\(b64)',null);}"
                print("[CameraCapture] Sending base64 result to JS (length: \(b64.count))")
                wv.evaluateJavaScript(js) { _, err in
                    if let err = err {
                        print("[CameraCapture] JS callback error: \(err.localizedDescription)")
                    } else {
                        print("[CameraCapture] JS callback executed successfully")
                    }
                }
            } else {
                let errMsg = (error ?? "Unknown error").replacingOccurrences(of: "'", with: "\\'")
                print("[CameraCapture] Sending error to JS: \(errMsg)")
                let js = "if(window._cameraCaptureCallback){window._cameraCaptureCallback('\(cbId)',null,'\(errMsg)');}"
                wv.evaluateJavaScript(js) { _, err in
                    if let err = err {
                        print("[CameraCapture] JS error callback error: \(err.localizedDescription)")
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
        print("[CameraCapture] Info keys: \(info.keys.map { $0.rawValue })")

        activePicker = nil
        picker.dismiss(animated: true) { [weak self] in
            guard let self = self else { return }

            guard let image = info[.originalImage] as? UIImage else {
                print("[CameraCapture] No original image in picker result")
                self.sendResult(nil, error: "No image captured")
                return
            }

            let w = image.size.width
            let h = image.size.height
            let orient = image.imageOrientation.rawValue
            print("[CameraCapture] Got image: \(w)x\(h), orientation: \(orient)")

            DispatchQueue.global(qos: .userInitiated).async {
                let normalized = self.normalizeOrientation(image)
                let resized = self.resizeIfNeeded(normalized, maxDimension: 1920)

                guard let jpegData = resized.jpegData(compressionQuality: 0.82) else {
                    print("[CameraCapture] JPEG compression failed")
                    self.sendResult(nil, error: "Image compression failed")
                    return
                }

                print("[CameraCapture] Compressed to \(jpegData.count) bytes (\(String(format: "%.1f", Double(jpegData.count)/1024.0)) KB)")
                let base64 = jpegData.base64EncodedString()
                print("[CameraCapture] Base64 length: \(base64.count)")
                self.sendResult(base64, error: nil)
            }
        }
    }

    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
        print("[CameraCapture] User cancelled")
        activePicker = nil
        picker.dismiss(animated: true) { [weak self] in
            self?.sendResult(nil, error: "cancelled")
        }
    }

    private func normalizeOrientation(_ image: UIImage) -> UIImage {
        guard image.imageOrientation != .up else { return image }

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1.0
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: image.size, format: format)
        return renderer.image { _ in
            image.draw(at: .zero)
        }
    }

    private func resizeIfNeeded(_ image: UIImage, maxDimension: CGFloat) -> UIImage {
        let w = image.size.width
        let h = image.size.height
        guard w > maxDimension || h > maxDimension else { return image }

        let ratio = min(maxDimension / w, maxDimension / h)
        let newSize = CGSize(width: round(w * ratio), height: round(h * ratio))

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1.0
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: newSize, format: format)
        return renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: newSize))
        }
    }
}
