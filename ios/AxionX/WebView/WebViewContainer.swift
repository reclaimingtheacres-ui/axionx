import SwiftUI
import WebKit

/// The main container that hosts the WKWebView.
/// Wires up the navigation delegate callbacks so connectivity state
/// is reflected back into SwiftUI without any polling.
/// Also surfaces a native Live Scan button when the agent is on an LPR page.
struct WebViewContainer: View {
    @StateObject private var store = WebViewStore()
    @State private var isOffline = false
    @State private var showLPRScanner = false
    @State private var currentURL: URL? = nil

    private var isOnLPRPage: Bool {
        guard let url = currentURL else { return false }
        return url.path.hasPrefix("/m/lpr")
    }

    var body: some View {
        ZStack(alignment: .topTrailing) {
            // WebView — always in the tree so session is never destroyed
            AxionWebView(store: store)
                .ignoresSafeArea()
                .opacity(isOffline ? 0 : 1)

            // Offline overlay
            if isOffline {
                OfflineView {
                    isOffline = false
                    store.reload()
                }
                .transition(.opacity)
            }

            // Native Live Scan button — visible only on /m/lpr pages
            if isOnLPRPage && !isOffline {
                Button(action: { showLPRScanner = true }) {
                    HStack(spacing: 6) {
                        Image(systemName: "camera.viewfinder")
                            .font(.system(size: 15, weight: .semibold))
                        Text("Live Scan")
                            .font(.system(size: 14, weight: .semibold))
                    }
                    .foregroundColor(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(Color(red: 0.15, green: 0.5, blue: 0.95))
                    .cornerRadius(20)
                    .shadow(color: .black.opacity(0.18), radius: 6, x: 0, y: 3)
                }
                .padding(.top, 56)
                .padding(.trailing, 16)
                .transition(.opacity.combined(with: .scale))
                .animation(.easeInOut(duration: 0.2), value: isOnLPRPage)
            }
        }
        .onAppear {
            wireDelegate()
            store.loadInitial()
        }
        .fullScreenCover(isPresented: $showLPRScanner) {
            LiveLPRScannerView(
                onPlateConfirmed: { plate in
                    showLPRScanner = false
                    navigateToLPRResult(plate: plate)
                },
                onCancel: {
                    showLPRScanner = false
                }
            )
        }
    }

    // MARK: - Private helpers

    private func wireDelegate() {
        store.navigationDelegate.onLoadFailed = {
            withAnimation { isOffline = true }
        }
        store.navigationDelegate.onLoadSuccess = {
            withAnimation { isOffline = false }
            currentURL = store.webView.url
        }
        // Observe URL changes so the Live Scan button shows/hides correctly
        store.webView.addObserver(
            URLObserver { url in
                DispatchQueue.main.async { currentURL = url }
            },
            forKeyPath: #keyPath(WKWebView.url),
            options: [.new],
            context: nil
        )
    }

    /// Navigate the web view to the LPR search page with the confirmed plate
    /// pre-filled as a URL parameter — the page auto-submits via JavaScript.
    private func navigateToLPRResult(plate: String) {
        var components = URLComponents()
        components.scheme = AppConfig.entryURL.scheme
        components.host   = AppConfig.entryURL.host
        components.path   = "/m/lpr"
        components.queryItems = [
            URLQueryItem(name: "plate",  value: plate),
            URLQueryItem(name: "method", value: "live_scan"),
        ]
        guard let url = components.url else { return }
        store.webView.load(URLRequest(url: url))
    }
}

// MARK: - Simple KVO observer shim

private final class URLObserver: NSObject {
    private let handler: (URL?) -> Void
    init(_ handler: @escaping (URL?) -> Void) { self.handler = handler }
    override func observeValue(forKeyPath keyPath: String?,
                               of object: Any?,
                               change: [NSKeyValueChangeKey: Any]?,
                               context: UnsafeMutableRawPointer?) {
        if keyPath == #keyPath(WKWebView.url),
           let wv = object as? WKWebView {
            handler(wv.url)
        }
    }
}
