import Foundation
import WebKit

final class BiometricSettingsHandler: NSObject, WKScriptMessageHandler {

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let webView = message.webView else { return }
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }

        let callbackId = body["callbackId"] as? String

        switch action {
        case "getStatus":
            let bioType = BiometricAuthService.biometricType
            let status: [String: Any] = [
                "available":    bioType != .none,
                "type":         bioType.settingsLabel,
                "enabled":      BiometricAuthService.isOptedIn,
                "hasToken":     BiometricAuthService.hasSavedToken,
                "declined":     BiometricAuthService.hasDeclined
            ]
            respondToWeb(webView: webView, callbackId: callbackId, data: status)

        case "enable":
            BiometricAuthService.setOptedIn(true)
            BiometricAuthService.setDeclined(false)
            respondToWeb(webView: webView, callbackId: callbackId, data: ["success": true])

        case "disable":
            BiometricAuthService.disableBiometric()
            respondToWeb(webView: webView, callbackId: callbackId, data: ["success": true])

        case "resetDecline":
            BiometricAuthService.setDeclined(false)
            respondToWeb(webView: webView, callbackId: callbackId, data: ["success": true])

        case "resetSession":
            BiometricAuthService.clearSession()
            respondToWeb(webView: webView, callbackId: callbackId, data: ["success": true])

        default:
            break
        }
    }

    private func respondToWeb(webView: WKWebView, callbackId: String?, data: [String: Any]) {
        guard let callbackId = callbackId else { return }
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data),
              let jsonStr = String(data: jsonData, encoding: .utf8) else { return }

        let js = "window._biometricCallback && window._biometricCallback('\(callbackId)', \(jsonStr));"
        DispatchQueue.main.async {
            webView.evaluateJavaScript(js, completionHandler: nil)
        }
    }
}
