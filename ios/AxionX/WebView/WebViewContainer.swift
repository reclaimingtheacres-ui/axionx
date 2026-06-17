import SwiftUI
import WebKit
import AVFoundation

/// The main container that hosts the WKWebView.
/// For live scans, intercepts the confirmed plate, calls the lookup API
/// natively, and presents LPRResultSheet so the agent never leaves the app
/// to see a result.  All other LPR entry paths (manual, photo OCR) continue
/// through the web layer unchanged.
///
/// Patrol mode: PatrolCameraService creates an AVCaptureVideoPreviewLayer and
/// signals this container via onPatrolActive.  The container inserts the layer
/// via PatrolPreviewView — a UIViewRepresentable placed at the bottom of the
/// ZStack, behind the WKWebView.  The WKWebView background is set to .clear
/// and CSS is injected to make the HTML body transparent, so the camera frames
/// are visible through the web page overlays (status bar, plate feed, controls).
struct WebViewContainer: View {
    @StateObject private var store = WebViewStore()
    @EnvironmentObject private var syncManager: SyncManager
    @EnvironmentObject private var fieldStatusManager: FieldStatusManager
    @ObservedObject  private var dispatchManager = DispatchManager.shared
    @State private var isOffline          = false
    @State private var showLPRScanner     = false
    @State private var isLookingUp        = false
    @State private var lprNativeResult: LPRResult? = nil
    @State private var currentURL: URL?   = nil
    @State private var showSyncStatus     = false
    @State private var showDispatchSheet  = false
    @State private var pendingDispatchId: Int? = nil
    /// Set when PatrolCameraService has an active preview layer ready to render.
    /// Nil at all other times — SwiftUI removes the PatrolPreviewView automatically.
    @State private var patrolPreviewLayer: AVCaptureVideoPreviewLayer? = nil

    private var isOnLPRPage: Bool {
        guard let url = currentURL else { return false }
        return url.path.hasPrefix("/m/lpr")
    }

    private var isOnPatrolPage: Bool {
        guard let url = currentURL else { return false }
        return url.path.hasPrefix("/m/lpr/patrol")
    }

    private var isActiveLPRCameraView: Bool {
        if showLPRScanner { return true }
        guard let path = currentURL?.path else { return false }
        return path == "/m/lpr/capture" || path.hasPrefix("/m/lpr/patrol")
    }

    private var shouldShowLPROverlays: Bool {
        isOnLPRPage && !isOffline && !isActiveLPRCameraView
    }

    var body: some View {
        ZStack(alignment: .topTrailing) {

            // ── Patrol camera preview ─────────────────────────────────────────
            // Rendered BELOW the WKWebView.  The WKWebView background is set to
            // .clear and the HTML body is made transparent via CSS injection so
            // the camera frames show through the web page UI overlays.
            if let layer = patrolPreviewLayer {
                PatrolPreviewView(previewLayer: layer)
                    .ignoresSafeArea()
            }

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
            if shouldShowLPROverlays && !isLookingUp {
                VStack(spacing: 8) {
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

                    if !isOnPatrolPage {
                        Button(action: { navigateToPatrol() }) {
                            HStack(spacing: 5) {
                                Image(systemName: "map")
                                    .font(.system(size: 13, weight: .semibold))
                                Text("Patrol")
                                    .font(.system(size: 13, weight: .semibold))
                            }
                            .foregroundColor(Color(red: 0.09, green: 0.36, blue: 0.67))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(Color(red: 0.94, green: 0.97, blue: 1.0))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(Color(red: 0.75, green: 0.86, blue: 0.99), lineWidth: 1)
                            )
                            .cornerRadius(16)
                            .shadow(color: .black.opacity(0.10), radius: 4, x: 0, y: 2)
                        }
                    }
                }
                .padding(.top, 56)
                .padding(.trailing, 16)
                .transition(.opacity.combined(with: .scale))
                .animation(.easeInOut(duration: 0.2), value: isOnLPRPage)
            }

            // Dispatch banner — shown on LPR pages when a follow-up is assigned and not yet accepted
            if shouldShowLPROverlays && dispatchManager.activeDispatch == nil
                && syncManager.assignedFollowupCount > 0 {
                VStack {
                    Spacer()
                    HStack(spacing: 0) {
                        Spacer()
                        Button(action: {
                            if let item = syncManager.lastAssignedFollowup {
                                pendingDispatchId = item.id
                                Task {
                                    await dispatchManager.fetchAndActivate(
                                        followupId: item.id,
                                        webView: store.webView
                                    )
                                    showDispatchSheet = true
                                }
                            }
                        }) {
                            HStack(spacing: 6) {
                                Image(systemName: "bell.badge.fill")
                                    .font(.system(size: 12, weight: .semibold))
                                let n = syncManager.assignedFollowupCount
                                Text(n == 1 ? "1 Follow-up Assigned" : "\(n) Follow-ups Assigned")
                                    .font(.system(size: 13, weight: .semibold))
                                Image(systemName: "chevron.up")
                                    .font(.system(size: 10, weight: .bold))
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 9)
                            .background(Color(red: 0.15, green: 0.50, blue: 0.95))
                            .cornerRadius(20)
                            .shadow(color: .black.opacity(0.2), radius: 4, x: 0, y: 2)
                        }
                        Spacer()
                    }
                    .padding(.bottom, 82)
                }
                .ignoresSafeArea(edges: .bottom)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .animation(.easeInOut(duration: 0.25), value: syncManager.assignedFollowupCount)
                .allowsHitTesting(true)
            }

            // Active dispatch banner — shown when a dispatch is in progress
            if let dispatch = dispatchManager.activeDispatch, !showDispatchSheet, !isActiveLPRCameraView {
                VStack {
                    Spacer()
                    HStack(spacing: 0) {
                        Spacer()
                        Button(action: { showDispatchSheet = true }) {
                            HStack(spacing: 6) {
                                let c = dispatch.priorityColor
                                Circle()
                                    .fill(Color(red: c.red, green: c.green, blue: c.blue))
                                    .frame(width: 8, height: 8)
                                Text(dispatch.actionLabel)
                                    .font(.system(size: 13, weight: .semibold))
                                Text("·")
                                    .foregroundStyle(.secondary)
                                Text(dispatch.sighting.registration.isEmpty
                                     ? "Plate unknown"
                                     : dispatch.sighting.registration)
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                Image(systemName: "chevron.up")
                                    .font(.system(size: 10, weight: .bold))
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 9)
                            .background(Color(red: 0.10, green: 0.10, blue: 0.12))
                            .cornerRadius(20)
                            .shadow(color: .black.opacity(0.25), radius: 5, x: 0, y: 2)
                        }
                        Spacer()
                    }
                    .padding(.bottom, 82)
                }
                .ignoresSafeArea(edges: .bottom)
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .animation(.easeInOut(duration: 0.2), value: dispatch.status)
                .allowsHitTesting(true)
            }

            // Sync badge — bottom-left, shown when there are pending or failed items
            if !isActiveLPRCameraView && (syncManager.pendingCount > 0 || syncManager.failedCount > 0) {
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
            print("[DIAG][WVC-ONAPPEAR] WebViewContainer.body.onAppear fired")
            print("[DIAG][WVC-ONAPPEAR] store.webView.url=\(store.webView.url?.absoluteString ?? "nil")")
            print("[DIAG][WVC-ONAPPEAR] isPreviewRestoreProtected=\(DocumentPreviewHandler.shared.isPreviewRestoreProtected)")
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
        .sheet(isPresented: $showDispatchSheet) {
            if let dispatch = dispatchManager.activeDispatch {
                DispatchSheet(dispatch: dispatch)
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.hidden)
            }
        }
        .onChange(of: dispatchManager.activeDispatch == nil) { isNil in
            if isNil { showDispatchSheet = false }
        }
        .onChange(of: isActiveLPRCameraView) { active in
            if active {
                showDispatchSheet = false
                showSyncStatus = false
            }
        }
        .onChange(of: currentURL) { _ in
            fieldStatusManager.isLPRContextActive = isOnLPRPage || showLPRScanner
        }
        .onChange(of: showLPRScanner) { scanning in
            fieldStatusManager.isLPRContextActive = scanning || isOnLPRPage
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .axionOpenNotifications)
        ) { notif in
            let notifType = notif.userInfo?["type"] as? String ?? "lpr"
            var comps    = URLComponents()
            comps.scheme = AppConfig.entryURL.scheme
            comps.host   = AppConfig.entryURL.host
            switch notifType {
            case "message":
                if let convId = notif.userInfo?["conv_id"] as? Int {
                    comps.path = "/m/messages/\(convId)"
                } else {
                    comps.path = "/m/messages"
                }
            default:
                comps.path = "/m/lpr/notifications"
            }
            if let url = comps.url {
                store.webView.load(URLRequest(url: url))
            }
            if notifType == "message" {
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                    PushNotificationService.shared.refreshUnreadBadge()
                }
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
            if let url = store.webView.url,
               url.path.hasPrefix("/m/login") || url.path == "/login" {
                NotificationCenter.default.post(name: .axionSessionExpired, object: nil)
                return
            }
            if let url = store.webView.url, url.path.hasPrefix("/m/messages") {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                    PushNotificationService.shared.refreshUnreadBadge()
                }
            }
        }
        store.webView.addObserver(
            URLObserver { url in
                DispatchQueue.main.async {
                    currentURL = url
                    if let u = url, !u.path.hasPrefix("/m/lpr/patrol") {
                        PatrolCameraService.shared.stopPatrol()
                    }
                    if let u = url, (u.path.hasPrefix("/m/lpr") || u.path.hasPrefix("/m/job/") || u.path.hasPrefix("/m/update-builder")) {
                        CameraPermissionService.shared.ensureCameraPermission()
                    }
                }
            },
            forKeyPath: #keyPath(WKWebView.url),
            options: [.new],
            context: nil
        )

        // ── Patrol preview layer callbacks ─────────────────────────────────────
        //
        // THREE properties must be cleared for the WKWebView to be truly
        // transparent, allowing PatrolPreviewView (behind it in the ZStack) to
        // show through:
        //   1. wv.isOpaque = false            — already set in WebViewStore.init()
        //   2. wv.backgroundColor = .clear    — set here
        //   3. wv.scrollView.backgroundColor = .clear  ← THE CRITICAL ONE
        //
        // WKScrollView is a UIScrollView subclass inside WKWebView with its own
        // backgroundColor.  Its default is .systemBackground (opaque white),
        // which blocks the PatrolPreviewView entirely — causing the black screen.
        // Setting wv.backgroundColor alone does NOT affect scrollView.backgroundColor.
        PatrolCameraService.shared.onPatrolActive = { layer in
            print("[WVC] onPatrolActive — clearing WKWebView + scrollView backgrounds, inserting preview layer")
            store.webView.isOpaque = false
            store.webView.backgroundColor = .clear
            store.webView.scrollView.isOpaque = false
            store.webView.scrollView.backgroundColor = .clear
            patrolPreviewLayer = layer
        }
        // Restore WKWebView and scrollView to their normal opaque state when
        // patrol stops (navigated away or Stop tapped).
        PatrolCameraService.shared.onPatrolStopped = {
            print("[WVC] onPatrolStopped — restoring WKWebView + scrollView backgrounds, removing preview layer")
            patrolPreviewLayer = nil
            store.webView.isOpaque = false         // keep false to prevent black flash on navigation
            store.webView.backgroundColor = .white
            store.webView.scrollView.isOpaque = true
            store.webView.scrollView.backgroundColor = .systemBackground
        }

        SyncManager.shared.setWebView(store.webView)
        PatrolCameraService.shared.setWebView(store.webView)
        DocumentPreviewHandler.shared.setWebView(store.webView)
        CameraPermissionService.shared.setWebView(store.webView)
        CameraCaptureService.shared.setWebView(store.webView)
        store.openSettingsHandler.setWebView(store.webView)
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

    private func navigateToPatrol() {
        var comps    = URLComponents()
        comps.scheme = AppConfig.entryURL.scheme
        comps.host   = AppConfig.entryURL.host
        comps.path   = "/m/lpr/patrol"
        guard let url = comps.url else { return }
        store.webView.load(URLRequest(url: url))
    }
}

// MARK: - Patrol camera preview view

/// UIView subclass that hosts an AVCaptureVideoPreviewLayer and keeps its
/// frame in sync with the view's bounds via layoutSubviews.
private final class PatrolPreviewHostView: UIView {
    let previewLayer: AVCaptureVideoPreviewLayer

    init(previewLayer: AVCaptureVideoPreviewLayer) {
        self.previewLayer = previewLayer
        super.init(frame: .zero)
        backgroundColor = .black
        previewLayer.videoGravity = .resizeAspectFill
        layer.addSublayer(previewLayer)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) not supported") }

    override func layoutSubviews() {
        super.layoutSubviews()
        CATransaction.begin()
        CATransaction.setAnimationDuration(0)
        previewLayer.frame = bounds
        CATransaction.commit()
    }
}

/// SwiftUI wrapper for PatrolPreviewHostView.
/// Placed at the bottom of the WebViewContainer ZStack so the camera
/// preview renders behind the (now-transparent) WKWebView.
private struct PatrolPreviewView: UIViewRepresentable {
    let previewLayer: AVCaptureVideoPreviewLayer

    func makeUIView(context: Context) -> PatrolPreviewHostView {
        PatrolPreviewHostView(previewLayer: previewLayer)
    }

    func updateUIView(_ uiView: PatrolPreviewHostView, context: Context) {
        // Layout is driven by layoutSubviews in PatrolPreviewHostView
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
