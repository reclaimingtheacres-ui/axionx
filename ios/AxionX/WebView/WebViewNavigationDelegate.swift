import UIKit
import WebKit
import AVFoundation

/// WKNavigationDelegate + WKUIDelegate implementation.
/// Controls all URL routing decisions and propagates load errors to SwiftUI.
final class WebViewNavigationDelegate: NSObject, WKNavigationDelegate, WKUIDelegate {

    /// Called by WebViewContainer when a load fails so the offline screen can be shown.
    var onLoadFailed: (() -> Void)?
    /// Called when a page loads successfully so the offline screen can be hidden.
    var onLoadSuccess: (() -> Void)?

    // MARK: - WKNavigationDelegate

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        // tel:, sms:, facetime: → system app
        if AllowedDomains.isNativeScheme(url) {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        // maps.apple.com / maps.google.com → Apple Maps
        if AllowedDomains.isMapsURL(url) {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        // External http/https → Safari
        if AllowedDomains.isExternalWeb(url) {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isTrusted(url),
           url.path.hasPrefix("/m/login") || url.path == "/login" {
            DispatchQueue.main.async {
                NotificationCenter.default.post(name: .axionSessionExpired, object: nil)
            }
            decisionHandler(.cancel)
            return
        }

        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        onLoadSuccess?()
        // Ensure page background stays white (prevents grey flash on overscroll)
        webView.evaluateJavaScript(
            "document.documentElement.style.backgroundColor='#ffffff';" +
            "document.body && (document.body.style.backgroundColor='#ffffff');",
            completionHandler: nil
        )
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        handleError(error)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        handleError(error)
    }

    private func handleError(_ error: Error) {
        let code = (error as NSError).code
        guard code != NSURLErrorCancelled else { return }  // Ignore user-cancelled loads
        onLoadFailed?()
    }

    // MARK: - WKUIDelegate

    /// Keep window.open() calls inside the WebView (open AxionX links in-app, others in Safari).
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if let url = navigationAction.request.url {
            if AllowedDomains.isTrusted(url) {
                webView.load(navigationAction.request)
            } else {
                UIApplication.shared.open(url)
            }
        }
        return nil
    }

    /// Native alert() support so JS dialogs work inside the WebView.
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        guard let vc = topViewController() else { completionHandler(); return }
        let alert = UIAlertController(title: AppConfig.displayName, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        vc.present(alert, animated: true)
    }

    /// Native confirm() support.
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard let vc = topViewController() else { completionHandler(false); return }
        let alert = UIAlertController(title: AppConfig.displayName, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
        vc.present(alert, animated: true)
    }

    // MARK: - Camera permission (iOS 15+)

    @available(iOS 15.0, *)
    func webView(
        _ webView: WKWebView,
        requestMediaCapturePermissionFor origin: WKSecurityOrigin,
        initiatedByFrame frame: WKFrameInfo,
        type: WKMediaCaptureType,
        decisionHandler: @escaping (WKPermissionDecision) -> Void
    ) {
        print("[WebView] requestMediaCapturePermissionFor called, type: \(type.rawValue)")
        let needsCamera = type == .camera || type == .cameraAndMicrophone
        let needsMic    = type == .microphone || type == .cameraAndMicrophone

        func checkAndRequest(
            mediaType: AVMediaType,
            then completion: @escaping (Bool) -> Void
        ) {
            let status = AVCaptureDevice.authorizationStatus(for: mediaType)
            print("[WebView] \(mediaType == .video ? "Camera" : "Mic") auth status: \(status.rawValue)")
            switch status {
            case .authorized:
                completion(true)
            case .notDetermined:
                print("[WebView] Requesting \(mediaType == .video ? "camera" : "mic") access")
                AVCaptureDevice.requestAccess(for: mediaType) { granted in
                    print("[WebView] \(mediaType == .video ? "Camera" : "Mic") access result: \(granted)")
                    DispatchQueue.main.async { completion(granted) }
                }
            case .denied, .restricted:
                completion(false)
            @unknown default:
                completion(false)
            }
        }

        func resolveCamera(_ cameraDone: @escaping (Bool) -> Void) {
            if needsCamera {
                checkAndRequest(mediaType: .video, then: cameraDone)
            } else {
                cameraDone(true)
            }
        }

        func resolveMic(_ micDone: @escaping (Bool) -> Void) {
            if needsMic {
                checkAndRequest(mediaType: .audio, then: micDone)
            } else {
                micDone(true)
            }
        }

        resolveCamera { cameraOk in
            resolveMic { micOk in
                let decision: WKPermissionDecision = (cameraOk && micOk) ? .grant : .deny
                print("[WebView] Media capture decision: \(decision == .grant ? "grant" : "deny")")
                decisionHandler(decision)
            }
        }
    }

    // MARK: - Private

    private func topViewController() -> UIViewController? {
        // UIWindowScene.keyWindow is the non-deprecated API from iOS 15+
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = scene.keyWindow else { return nil }
        var vc = window.rootViewController
        while let presented = vc?.presentedViewController { vc = presented }
        return vc
    }
}
