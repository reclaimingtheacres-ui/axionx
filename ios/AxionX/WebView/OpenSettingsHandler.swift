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
            print("[OpenSettings] App became active, refreshing webview")

            CameraPermissionService.shared.ensureCameraPermission()

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                guard let wv = self.webView else { return }
                if let saved = savedURL {
                    wv.load(URLRequest(url: saved))
                } else {
                    wv.reload()
                }
            }
        }

        UIApplication.shared.open(url)
    }
}
