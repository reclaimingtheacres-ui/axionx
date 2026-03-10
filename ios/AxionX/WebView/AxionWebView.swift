import SwiftUI
import WebKit

/// Holds the shared WKWebView instance so multiple SwiftUI views can
/// reference and control it without recreating it.
final class WebViewStore: ObservableObject {
    let webView: WKWebView
    let navigationDelegate: WebViewNavigationDelegate

    init() {
        let config = WKWebViewConfiguration()
        // Persist cookies and localStorage across app launches
        config.websiteDataStore = .default()
        config.applicationNameForUserAgent = AppConfig.userAgent
        config.allowsInlineMediaPlayback = true
        // Required so getUserMedia works without a user gesture on every call
        config.mediaTypesRequiringUserActionForPlayback = []

        let biometricHandler = BiometricSettingsHandler()
        config.userContentController.add(biometricHandler, name: "biometricSettings")

        let wv = WKWebView(frame: .zero, configuration: config)
        wv.backgroundColor = .white
        wv.isOpaque = false   // Prevents black flash before page paints
        wv.scrollView.contentInsetAdjustmentBehavior = .never
        wv.scrollView.bounces = true

        let delegate = WebViewNavigationDelegate()
        wv.navigationDelegate = delegate
        wv.uiDelegate = delegate

        self.webView = wv
        self.navigationDelegate = delegate
        self.biometricHandler = biometricHandler
    }

    private let biometricHandler: BiometricSettingsHandler

    func loadInitial() {
        webView.load(URLRequest(
            url: AppConfig.entryURL,
            cachePolicy: .useProtocolCachePolicy,
            timeoutInterval: 20
        ))
    }

    func reload() {
        if webView.url != nil {
            webView.reload()
        } else {
            loadInitial()
        }
    }
}

/// UIViewRepresentable that embeds the shared WKWebView into a SwiftUI hierarchy.
struct AxionWebView: UIViewRepresentable {
    @ObservedObject var store: WebViewStore

    func makeUIView(context: Context) -> WKWebView {
        store.webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        // Intentionally empty — the store owns lifecycle
    }
}
