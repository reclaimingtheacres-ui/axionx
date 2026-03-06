import UIKit
import WebKit
import CoreLocation

class WebViewController: UIViewController {

    // MARK: - Properties

    private var webView: WKWebView!
    private var offlineVC: OfflineViewController?
    private let locationManager = LocationPermissionManager.shared
    private var hasLoadedOnce = false

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white
        setupWebView()
        loadAxionX()
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .darkContent }

    // MARK: - Setup

    private func setupWebView() {
        let config = WKWebViewConfiguration()

        // Full cookie + storage support for session persistence
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        // User agent — identifies app to the server for future native features
        config.applicationNameForUserAgent = "AxionXiOS/1.0"

        webView = WKWebView(frame: .zero, configuration: config)
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.backgroundColor = .white
        webView.isOpaque = false   // Prevents black flash before page loads
        webView.scrollView.contentInsetAdjustmentBehavior = .never

        view.addSubview(webView)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
    }

    // MARK: - Loading

    func loadAxionX() {
        let request = URLRequest(
            url: AppConfig.startURL,
            cachePolicy: .useProtocolCachePolicy,
            timeoutInterval: 20
        )
        webView.load(request)
    }

    /// Called from SceneDelegate when app returns to foreground
    func resumeIfNeeded() {
        guard hasLoadedOnce else { return }
        // If webView is showing a blank page (e.g. was killed in background), reload
        if webView.url == nil || webView.isLoading == false && webView.title?.isEmpty == true {
            loadAxionX()
        }
    }

    // MARK: - Offline screen

    private func showOfflineScreen() {
        guard offlineVC == nil else { return }
        let vc = OfflineViewController()
        vc.onRetry = { [weak self] in
            self?.hideOfflineScreen()
            self?.loadAxionX()
        }
        addChild(vc)
        vc.view.frame = view.bounds
        vc.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(vc.view)
        vc.didMove(toParent: self)
        offlineVC = vc
    }

    private func hideOfflineScreen() {
        offlineVC?.willMove(toParent: nil)
        offlineVC?.view.removeFromSuperview()
        offlineVC?.removeFromParent()
        offlineVC = nil
    }

    // MARK: - URL Classification

    private func isAxionXHost(_ url: URL) -> Bool {
        guard let host = url.host else { return false }
        return AppConfig.allowedHosts.contains(host) || AppConfig.allowedHosts.contains("www.\(host)")
    }

    private func isNativeScheme(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased() else { return false }
        return AppConfig.nativeSchemes.contains(scheme)
    }

    private func isMapsURL(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return AppConfig.mapsHosts.contains(host)
    }

    private func isExternalHTTP(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased() else { return false }
        guard scheme == "http" || scheme == "https" else { return false }
        return !isAxionXHost(url)
    }
}

// MARK: - WKNavigationDelegate

extension WebViewController: WKNavigationDelegate {

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        // tel:, sms:, facetime: → native apps
        if isNativeScheme(url) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            decisionHandler(.cancel)
            return
        }

        // maps.apple.com or maps.google.com → Apple Maps
        if isMapsURL(url) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            decisionHandler(.cancel)
            return
        }

        // External HTTP/HTTPS links → Safari
        if isExternalHTTP(url) {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            decisionHandler(.cancel)
            return
        }

        // AxionX /m/* or allowed host → stay in app
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        hasLoadedOnce = true
        hideOfflineScreen()

        // Inject CSS to prevent rubber-band bounce exposing white/grey gap
        let js = """
        document.documentElement.style.backgroundColor = '#ffffff';
        document.body.style.backgroundColor = '#ffffff';
        """
        webView.evaluateJavaScript(js, completionHandler: nil)
    }

    func webView(
        _ webView: WKWebView,
        didFail navigation: WKNavigation!,
        withError error: Error
    ) {
        handleNavigationError(error)
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
        handleNavigationError(error)
    }

    private func handleNavigationError(_ error: Error) {
        let nsError = error as NSError
        // Ignore cancelled navigations (e.g. user tapped a link before page loaded)
        guard nsError.code != NSURLErrorCancelled else { return }
        showOfflineScreen()
    }

    // Handle HTTP auth challenges (e.g. dev basic auth)
    func webView(
        _ webView: WKWebView,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        completionHandler(.performDefaultHandling, nil)
    }
}

// MARK: - WKUIDelegate

extension WebViewController: WKUIDelegate {

    // Handle window.open() — keep navigation in the same WebView
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if let url = navigationAction.request.url {
            if isAxionXHost(url) {
                webView.load(navigationAction.request)
            } else {
                UIApplication.shared.open(url, options: [:], completionHandler: nil)
            }
        }
        return nil
    }

    // Native alert support for JS alert()
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = UIAlertController(title: AppConfig.displayName, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        present(alert, animated: true)
    }

    // Native confirm support for JS confirm()
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = UIAlertController(title: AppConfig.displayName, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
        present(alert, animated: true)
    }
}
