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

        let ext = url.pathExtension.lowercased()
        let navType = navigationAction.navigationType
        let isMainFrame = navigationAction.targetFrame?.isMainFrame ?? true
        print("[NavDelegate] decidePolicyFor: \(url.absoluteString)")
        print("[NavDelegate]   ext='\(ext)' navType=\(navType.rawValue) isMainFrame=\(isMainFrame)")

        if DocumentPreviewHandler.shared.shouldBlockNavigation(to: url, reason: "navigation action") {
            print("[NavDelegate]   → CANCEL (blocked during document preview/restore)")
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isNativeScheme(url) {
            print("[NavDelegate]   → CANCEL (native scheme)")
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isMapsURL(url) {
            print("[NavDelegate]   → CANCEL (maps URL)")
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isExternalWeb(url) {
            print("[NavDelegate]   → CANCEL (external web)")
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        if Self.documentExtensions.contains(ext)
            && AllowedDomains.isTrusted(url)
            && navType == .linkActivated {
            let filename = url.lastPathComponent
            print("[NavDelegate]   → CANCEL (document link: \(filename))")
            DocumentPreviewHandler.shared.captureReturnURL(from: webView.url, reason: "document extension link before cancel")
            DocumentPreviewHandler.shared.previewFile(at: url, filename: filename)
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isTrusted(url) && Self.isDocumentPreviewPath(url) {
            let filename = url.lastPathComponent
            print("[NavDelegate]   → CANCEL (document preview route: \(url.path)) navType=\(navType.rawValue)")
            print("[NavDelegate]   PDF_REQUEST_INTERCEPT = YES")
            print("[NavDelegate]   web modal/viewer attempt intercepted before web load")
            DocumentPreviewHandler.shared.captureReturnURL(from: webView.url, reason: "document preview route before cancel")
            DocumentPreviewHandler.shared.previewFile(at: url, filename: filename)
            decisionHandler(.cancel)
            return
        }

        if AllowedDomains.isTrusted(url),
           url.path.hasPrefix("/m/login") || url.path == "/login" {
            print("[NavDelegate]   → CANCEL (login redirect detected)")
            DispatchQueue.main.async {
                NotificationCenter.default.post(name: .axionSessionExpired, object: nil)
            }
            decisionHandler(.cancel)
            return
        }

        print("[NavDelegate]   → ALLOW")
        decisionHandler(.allow)
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationResponse: WKNavigationResponse,
        decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
    ) {
        let responseURL = navigationResponse.response.url
        let mime = (navigationResponse.response as? HTTPURLResponse)?.mimeType ?? navigationResponse.response.mimeType ?? "unknown"
        let statusCode = (navigationResponse.response as? HTTPURLResponse)?.statusCode ?? -1
        let isMainFrame = navigationResponse.isForMainFrame

        print("[NavDelegate] ── decidePolicyFor RESPONSE ──")
        print("[NavDelegate]   url=\(responseURL?.absoluteString ?? "nil")")
        print("[NavDelegate]   mime=\(mime)")
        print("[NavDelegate]   status=\(statusCode)")
        print("[NavDelegate]   isMainFrame=\(isMainFrame)")

        if let http = navigationResponse.response as? HTTPURLResponse {
            let cd = http.value(forHTTPHeaderField: "Content-Disposition") ?? "none"
            let ct = http.value(forHTTPHeaderField: "Content-Type") ?? "none"
            print("[NavDelegate]   Content-Type header=\(ct)")
            print("[NavDelegate]   Content-Disposition=\(cd)")
        }

        guard let url = responseURL else {
            print("[NavDelegate]   → ALLOW (no URL)")
            decisionHandler(.allow)
            return
        }

        if DocumentPreviewHandler.shared.shouldBlockNavigation(to: url, reason: "navigation response") {
            print("[NavDelegate]   → CANCEL RESPONSE (blocked during document preview/restore)")
            decisionHandler(.cancel)
            return
        }

        let isTrusted = AllowedDomains.isTrusted(url)
        let isPreviewRoute = Self.isDocumentPreviewPath(url)
        let mimeLower = mime.lowercased()
        let isDocMime = mimeLower == "application/pdf"
            || mimeLower == "application/msword"
            || mimeLower.contains("officedocument")
            || mimeLower == "application/octet-stream"

        print("[NavDelegate]   isTrusted=\(isTrusted)")
        print("[NavDelegate]   isPreviewRoute=\(isPreviewRoute)")
        print("[NavDelegate]   isDocMime=\(isDocMime)")

        if isTrusted && (isPreviewRoute || isDocMime) {
            print("[NavDelegate]   ╔══════════════════════════════════════╗")
            print("[NavDelegate]   ║  PDF_INTERCEPT_ACTIVE = YES          ║")
            print("[NavDelegate]   ╚══════════════════════════════════════╝")
            print("[NavDelegate]   web modal/viewer response intercepted isMainFrame=\(isMainFrame)")

            let cd = (navigationResponse.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
            var filename = url.lastPathComponent
            if let cdName = Self.extractContentDispositionFilename(cd) {
                filename = cdName
            }
            print("[NavDelegate]   resolved filename=\(filename)")
            print("[NavDelegate]   calling decisionHandler(.cancel)")
            decisionHandler(.cancel)
            print("[NavDelegate]   calling DocumentPreviewHandler.previewFile")
            DocumentPreviewHandler.shared.captureReturnURL(from: webView.url, reason: "document response before cancel")
            DocumentPreviewHandler.shared.previewFile(at: url, filename: filename)
            return
        }

        print("[NavDelegate]   → ALLOW")
        decisionHandler(.allow)
    }

    private static func extractContentDispositionFilename(_ cd: String) -> String? {
        let patterns = [
            "filename=\"([^\"]+)\"",
            "filename=([^;\\s]+)"
        ]
        for pattern in patterns {
            if let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive),
               let match = regex.firstMatch(in: cd, range: NSRange(cd.startIndex..., in: cd)),
               match.numberOfRanges > 1,
               let range = Range(match.range(at: 1), in: cd) {
                return String(cd[range]).removingPercentEncoding ?? String(cd[range])
            }
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        onLoadSuccess?()
        // Ensure page background stays white (prevents grey flash on overscroll)
        webView.evaluateJavaScript(
            "document.documentElement.style.backgroundColor='#ffffff';" +
            "document.body && (document.body.style.backgroundColor='#ffffff');",
            completionHandler: nil
        )
        if let url = webView.url {
            DocumentPreviewHandler.shared.noteNavigationFinished(url)
            if DocumentPreviewHandler.shared.canTrackReturnURL,
               DocumentPreviewHandler.isRestorableReturnURL(url) {
                DocumentPreviewHandler.shared.setReturnURL(url, reason: "successful page load")
                print("[NavDelegate] Return URL tracked after load: \(url.absoluteString)")
            }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        let nsError = error as NSError
        print("[NavDelegate] didFail: domain=\(nsError.domain) code=\(nsError.code) desc=\(nsError.localizedDescription)")
        handleError(error)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        let nsError = error as NSError
        print("[NavDelegate] didFailProvisional: domain=\(nsError.domain) code=\(nsError.code) desc=\(nsError.localizedDescription)")
        handleError(error)
    }

    private func handleError(_ error: Error) {
        let code = (error as NSError).code
        guard code != NSURLErrorCancelled else {
            print("[NavDelegate] Ignoring cancelled navigation (code -999)")
            return
        }
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
            let ext = url.pathExtension.lowercased()
            print("[NavDelegate] createWebViewWith (window.open): \(url.absoluteString) ext='\(ext)'")
            if AllowedDomains.isTrusted(url) {
                if Self.documentExtensions.contains(ext) || Self.isDocumentPreviewPath(url) {
                    let filename = url.lastPathComponent
                    print("[NavDelegate]   → document preview: \(filename)")
                    print("[NavDelegate]   web modal/window.open attempt intercepted")
                    DocumentPreviewHandler.shared.captureReturnURL(from: webView.url, reason: "window.open document before cancel")
                    DocumentPreviewHandler.shared.previewFile(at: url, filename: filename)
                } else {
                    print("[NavDelegate]   → loading in webview")
                    webView.load(navigationAction.request)
                }
            } else {
                print("[NavDelegate]   → opening externally")
                UIApplication.shared.open(url)
            }
        }
        return nil
    }

    private static let documentExtensions: Set<String> = [
        "pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "rtf"
    ]

    private static func isDocumentPreviewPath(_ url: URL) -> Bool {
        return DocumentPreviewHandler.isDocumentPreviewURL(url)
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
