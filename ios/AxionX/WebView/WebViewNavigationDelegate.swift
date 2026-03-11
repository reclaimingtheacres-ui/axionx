import UIKit
import WebKit

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

    /// WKWebView calls this before allowing getUserMedia / camera access from web JS.
    /// Without this delegate method WKWebView silently denies the request every time,
    /// even if the host app has NSCameraUsageDescription and the user granted camera
    /// permission in iOS Settings.  We grant unconditionally — the user already approved
    /// camera access at the native iOS level when the OS prompt was accepted.
    @available(iOS 15.0, *)
    func webView(
        _ webView: WKWebView,
        requestMediaCapturePermissionFor origin: WKSecurityOrigin,
        initiatedByFrame frame: WKFrameInfo,
        type: WKMediaCaptureType,
        decisionHandler: @escaping (WKPermissionDecision) -> Void
    ) {
        decisionHandler(.grant)
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
