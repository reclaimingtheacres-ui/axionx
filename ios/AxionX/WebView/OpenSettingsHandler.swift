import UIKit
import WebKit

final class OpenSettingsHandler: NSObject, WKScriptMessageHandler {

    private weak var webView: WKWebView?
    private var observerToken: NSObjectProtocol?

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        print("[OpenSettings] Opening app settings")
        guard let url = URL(string: UIApplication.openSettingsURLString) else { return }

        let savedURL = webView?.url

        observerToken.map { NotificationCenter.default.removeObserver($0) }
        observerToken = NotificationCenter.default.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            guard let self = self else { return }
            if let token = self.observerToken {
                NotificationCenter.default.removeObserver(token)
                self.observerToken = nil
            }
            print("[OpenSettings] App became active, refreshing camera status")

            CameraPermissionService.shared.ensureCameraPermission()

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                guard let wv = self.webView else { return }
                let checkJS = "typeof window.axRetryCamera === 'function'"
                wv.evaluateJavaScript(checkJS) { result, error in
                    if error == nil, let hasHandler = result as? Bool, hasHandler {
                        print("[OpenSettings] Page alive, axRetryCamera present — triggering camera retry via JS")
                        wv.evaluateJavaScript("window.axRetryCamera()") { _, _ in }
                    } else if error == nil {
                        print("[OpenSettings] Page alive but no axRetryCamera — status already pushed, reloading")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            guard let wv2 = self.webView else { return }
                            if let saved = savedURL {
                                wv2.load(URLRequest(url: saved))
                            } else {
                                wv2.reload()
                            }
                        }
                    } else {
                        print("[OpenSettings] Page unresponsive or no JS handler — reloading")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                            guard let wv2 = self.webView else { return }
                            if let saved = savedURL {
                                wv2.load(URLRequest(url: saved))
                            } else {
                                wv2.reload()
                            }
                        }
                    }
                }
            }
        }

        UIApplication.shared.open(url)
    }
}
