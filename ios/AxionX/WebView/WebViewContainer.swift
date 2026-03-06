import SwiftUI
import WebKit

/// The main container that hosts the WKWebView.
/// For live scans, intercepts the confirmed plate, calls the lookup API
/// natively, and presents LPRResultSheet so the agent never leaves the app
/// to see a result.  All other LPR entry paths (manual, photo OCR) continue
/// through the web layer unchanged.
struct WebViewContainer: View {
    @StateObject private var store = WebViewStore()
    @EnvironmentObject private var syncManager: SyncManager
    @EnvironmentObject private var fieldStatusManager: FieldStatusManager
    @State private var isOffline         = false
    @State private var showLPRScanner    = false
    @State private var isLookingUp       = false
    @State private var lprNativeResult: LPRResult? = nil
    @State private var currentURL: URL?  = nil
    @State private var showSyncStatus    = false

    private var isOnLPRPage: Bool {
        guard let url = currentURL else { return false }
        return url.path.hasPrefix("/m/lpr")
    }

    var body: some View {
        ZStack(alignment: .topTrailing) {
            AxionWebView(store: store)
                .ignoresSafeArea()
                .opacity(isOffline ? 0 : 1)

            if isOffline {
                OfflineView {
                    isOffline = false
                    store.reload()
                }
                .transition(.opacity)
            }

            // Loading spinner while native lookup is in flight
            if isLookingUp {
                ZStack {
                    Color.black.opacity(0.45).ignoresSafeArea()
                    VStack(spacing: 14) {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(1.4)
                        Text("Looking up plate…")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(.white)
                    }
                    .padding(28)
                    .background(.ultraThinMaterial)
                    .cornerRadius(18)
                }
                .transition(.opacity)
            }

            // Floating Live Scan button — visible on /m/lpr* pages
            if isOnLPRPage && !isOffline && !isLookingUp {
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

            // Field Status Control — bottom centre, shown on LPR pages
            if isOnLPRPage && !isOffline {
                VStack {
                    Spacer()
                    FieldStatusView()
                        .padding(.bottom, syncManager.pendingCount + syncManager.failedCount > 0 ? 56 : 24)
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .allowsHitTesting(true)
                .ignoresSafeArea(edges: .bottom)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .animation(.easeInOut(duration: 0.2), value: isOnLPRPage)
            }

            // Sync badge — bottom-left, shown when there are pending or failed items
            if syncManager.pendingCount > 0 || syncManager.failedCount > 0 {
                VStack {
                    Spacer()
                    HStack {
                        Button(action: { showSyncStatus = true }) {
                            HStack(spacing: 5) {
                                Image(systemName: syncManager.failedCount > 0
                                      ? "exclamationmark.circle.fill"
                                      : "arrow.triangle.2.circlepath")
                                    .font(.system(size: 11, weight: .semibold))
                                let total = syncManager.pendingCount + syncManager.failedCount
                                Text(total == 1 ? "1 pending" : "\(total) pending")
                                    .font(.system(size: 12, weight: .semibold))
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(syncManager.failedCount > 0 ? Color.red : Color.orange)
                            .cornerRadius(20)
                            .shadow(color: .black.opacity(0.2), radius: 3, x: 0, y: 2)
                        }
                        Spacer()
                    }
                    .padding(.leading, 16)
                    .padding(.bottom, 20)
                }
                .ignoresSafeArea(edges: .bottom)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .animation(.easeInOut(duration: 0.25), value: syncManager.pendingCount + syncManager.failedCount)
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
                    performNativeLookup(plate: plate)
                },
                onCancel: {
                    showLPRScanner = false
                }
            )
        }
        .sheet(item: Binding(
            get: { lprNativeResult.map { IdentifiableResult($0) } },
            set: { if $0 == nil { lprNativeResult = nil } }
        )) { wrapper in
            LPRResultSheet(
                result:   wrapper.result,
                webView:  store.webView,
                onOpenJob: { urlStr in
                    lprNativeResult = nil
                    if let url = URL(string: urlStr) {
                        store.webView.load(URLRequest(url: url))
                    }
                },
                onDismiss: {
                    lprNativeResult = nil
                }
            )
        }
        .sheet(isPresented: $showSyncStatus) {
            SyncStatusView()
                .environmentObject(syncManager)
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .axionOpenNotifications)
        ) { _ in
            var comps    = URLComponents()
            comps.scheme = AppConfig.entryURL.scheme
            comps.host   = AppConfig.entryURL.host
            comps.path   = "/m/lpr/notifications"
            if let url = comps.url {
                store.webView.load(URLRequest(url: url))
            }
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
        store.webView.addObserver(
            URLObserver { url in
                DispatchQueue.main.async { currentURL = url }
            },
            forKeyPath: #keyPath(WKWebView.url),
            options: [.new],
            context: nil
        )
        // Give the sync manager access to the shared webView session
        SyncManager.shared.setWebView(store.webView)
    }

    /// Call the lookup API natively using the webview's session cookies.
    /// On success, present the native result sheet.
    /// On failure (network/auth), fall back to the web form approach.
    private func performNativeLookup(plate: String) {
        guard !isLookingUp else { return }
        withAnimation { isLookingUp = true }

        LPRAPIClient.lookup(plate: plate, method: "live_scan", webView: store.webView) { result in
            withAnimation { isLookingUp = false }
            if let result = result {
                lprNativeResult = result
            } else {
                // API unreachable or unauthenticated — fall back to URL-param submission
                submitPlateViaURL(plate: plate)
            }
        }
    }

    /// URL-param fallback: loads /m/lpr?plate=…&method=live_scan.
    /// The page's JS auto-submits when it sees the plate param.
    private func submitPlateViaURL(plate: String) {
        let safe = plate.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? plate
        var comps        = URLComponents()
        comps.scheme     = AppConfig.entryURL.scheme
        comps.host       = AppConfig.entryURL.host
        comps.path       = "/m/lpr"
        comps.queryItems = [
            URLQueryItem(name: "plate",  value: safe),
            URLQueryItem(name: "method", value: "live_scan"),
        ]
        guard let url = comps.url else { return }
        store.webView.load(URLRequest(url: url))
    }
}

// MARK: - Identifiable wrapper for the sheet binding

private struct IdentifiableResult: Identifiable {
    let id = UUID()
    let result: LPRResult
    init(_ result: LPRResult) { self.result = result }
}

// MARK: - KVO observer shim

private final class URLObserver: NSObject {
    private let handler: (URL?) -> Void
    init(_ handler: @escaping (URL?) -> Void) { self.handler = handler }
    override func observeValue(forKeyPath keyPath: String?,
                               of object: Any?,
                               change: [NSKeyValueChangeKey: Any]?,
                               context: UnsafeMutableRawPointer?) {
        if keyPath == #keyPath(WKWebView.url), let wv = object as? WKWebView {
            handler(wv.url)
        }
    }
}
