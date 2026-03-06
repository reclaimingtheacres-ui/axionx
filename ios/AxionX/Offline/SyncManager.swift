import Foundation
import Combine
import Network
import WebKit

// MARK: - Sync Manager
//
// Singleton ObservableObject that:
//  • Holds a weak reference to the shared WKWebView (for cookie-authenticated requests)
//  • Monitors network via NWPathMonitor and auto-syncs when connectivity returns
//  • Exposes @Published state for badge and SyncStatusView
//  • All mutations happen on MainActor

@MainActor
final class SyncManager: ObservableObject {

    static let shared = SyncManager()

    // MARK: - Published state

    @Published var pendingCount:          Int  = 0
    @Published var failedCount:           Int  = 0
    @Published var isSyncing:             Bool = false
    @Published var lastSyncAt:            Date? = nil
    @Published var assignedFollowupCount: Int  = 0

    // MARK: - Internals

    private let queue        = OfflineQueue.shared
    private weak var webView: WKWebView?

    private let monitor      = NWPathMonitor()
    private let monitorQ     = DispatchQueue(label: "com.axionx.sync.net", qos: .utility)
    private var wasOffline   = false

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let connected = path.status == .satisfied
            DispatchQueue.main.async {
                guard let self else { return }
                if connected && self.wasOffline {
                    self.wasOffline = false
                    Task { await self.syncNow() }
                } else if !connected {
                    self.wasOffline = true
                }
            }
        }
        monitor.start(queue: monitorQ)
        refreshCounts()
    }

    // MARK: - WebView binding (called from WebViewContainer.onAppear)

    func setWebView(_ wv: WKWebView) {
        webView = wv
        Task { await syncNow() }       // drain any pending items immediately
    }

    // MARK: - Count refresh

    func refreshCounts() {
        pendingCount = queue.pendingCount
        failedCount  = queue.failedCount
    }

    // MARK: - Computed queue snapshots (for SyncStatusView)

    var pendingItems: [OfflineQueueItem] { queue.pendingItems  }
    var failedItems:  [OfflineQueueItem] { queue.failedItems   }
    var recentItems:  [OfflineQueueItem] { queue.recentSuccessItems }

    // MARK: - Enqueue helpers

    func enqueueSaveSighting(payload: [String: String], clientActionId: String) {
        queue.enqueue(OfflineQueueItem(
            clientActionId: clientActionId,
            actionType:     "save_sighting",
            payload:        payload
        ))
        refreshCounts()
    }

    func enqueueDeviceRegister(token: String) {
        queue.enqueue(OfflineQueueItem(
            actionType: "register_device",
            payload:    ["token": token, "platform": "ios"]
        ))
        refreshCounts()
    }

    func enqueueMarkNotificationsRead() {
        queue.enqueue(OfflineQueueItem(
            actionType: "mark_notifications_read",
            payload:    [:]
        ))
        refreshCounts()
    }

    /// Queue a follow-up status update. Transparent to the pending badge.
    func enqueueFollowupStatusUpdate(followupId: Int, status: String) {
        queue.enqueue(OfflineQueueItem(
            actionType: "followup_status",
            payload: [
                "followup_id": "\(followupId)",
                "status":      status,
            ]
        ))
        // Don't bump the badge — this is a background operational update
    }

    /// Queue a location ping. Counts are not refreshed (pings are transparent to the badge).
    func enqueueLocationPing(lat: Double, lng: Double, accuracy: Double,
                              battery: String, context: String,
                              source: String, capturedAt: String) {
        queue.enqueue(OfflineQueueItem(
            actionType: "location_ping",
            payload: [
                "lat":           "\(lat)",
                "lng":           "\(lng)",
                "accuracy":      "\(accuracy)",
                "battery_state": battery,
                "context":       context,
                "source":        source,
                "captured_at":   capturedAt,
            ]
        ))
        // Don't show location pings in the sync badge — they are silent background items
    }

    // MARK: - Sync

    func syncNow() async {
        guard !isSyncing, let wv = webView else {
            refreshCounts()
            return
        }
        let pending = queue.pendingItems
        if pending.isEmpty {
            lastSyncAt = Date()
            await refreshRemoteState(webView: wv)
            return
        }

        isSyncing = true

        for item in pending {
            queue.markSyncing(item.clientActionId)
            let ok = await processItem(item, webView: wv)
            if ok {
                queue.markSuccess(item.clientActionId)
            } else {
                let err = item.retryCount >= 4 ? "Max retries exceeded" : "Network unavailable"
                queue.markFailed(item.clientActionId, error: err)
            }
            refreshCounts()
        }

        isSyncing   = false
        lastSyncAt  = Date()
        await refreshRemoteState(webView: wv)
        refreshCounts()
    }

    func retryFailed() async {
        for item in queue.failedItems where item.retryCount < 10 {
            queue.resetToPending(item.clientActionId)
        }
        refreshCounts()
        await syncNow()
    }

    // MARK: - Last assigned follow-up (for dispatch banner tap)

    /// The most recently assigned, non-completed follow-up from the last remote refresh.
    /// Stored as a lightweight summary — no customer data.
    private(set) var assignedFollowupItems: [AssignedFollowupItem] = []

    var lastAssignedFollowup: AssignedFollowupItem? { assignedFollowupItems.first }

    // MARK: - Remote state refresh (badge + follow-up count)

    private func refreshRemoteState(webView: WKWebView) async {
        PushNotificationService.shared.refreshUnreadBadge()
        do {
            let json = try await fetchJSON(path: "/m/api/lpr/assigned-followups",
                                           webView: webView)
            assignedFollowupCount = json["count"] as? Int ?? 0
            if let items = json["items"] as? [[String: Any]] {
                assignedFollowupItems = items.compactMap { d in
                    guard let id = d["id"] as? Int,
                          let at = d["action_type"] as? String,
                          let pri = d["priority"] as? String else { return nil }
                    return AssignedFollowupItem(
                        id:         id,
                        actionType: at,
                        priority:   pri,
                        status:     d["status"] as? String ?? "assigned",
                        lat:        d["latitude"] as? Double,
                        lng:        d["longitude"] as? Double
                    )
                }
            }
        } catch {}

        // Opportunistic patrol rescoring — runs only when the ML model is bundled
        // and the 6-hour cooldown has elapsed.  Completely silent; never blocks UI.
        PatrolPredictionService.shared.runBatchScoringIfNeeded(webView: webView)
    }

    // MARK: - Item processing

    private func processItem(_ item: OfflineQueueItem, webView: WKWebView) async -> Bool {
        switch item.actionType {
        case "save_sighting":           return await syncSaveSighting(item, webView: webView)
        case "register_device":         return await syncPost(item,
                                                              path: "/m/api/device/register",
                                                              webView: webView)
        case "mark_notifications_read": return await syncPost(item,
                                                              path: "/m/api/lpr/notifications/read",
                                                              webView: webView)
        case "location_ping":           return await syncPost(item,
                                                              path: "/m/api/location/ping",
                                                              webView: webView)
        case "followup_status":
            guard let idStr = item.payload["followup_id"],
                  let followupId = Int(idStr) else { return true }
            return await syncPost(item,
                                  path: "/m/api/lpr/followup/\(followupId)/status",
                                  webView: webView)
        default:                        return true  // discard unknown action types
        }
    }

    private func syncSaveSighting(_ item: OfflineQueueItem, webView: WKWebView) async -> Bool {
        var body: [String: Any] = ["client_action_id": item.clientActionId]
        for (k, v) in item.payload { body[k] = v }
        // Re-parse typed fields from string storage
        if let s = item.payload["latitude"],             let d = Double(s) { body["latitude"]  = d }
        if let s = item.payload["longitude"],            let d = Double(s) { body["longitude"] = d }
        if let s = item.payload["escalated_to_office"]               { body["escalated_to_office"] = s == "1" }
        if let s = item.payload["watchlist_hit"]                     { body["watchlist_hit"]       = s == "1" }
        if let s = item.payload["matched_job_id"], let n = Int(s)    { body["matched_job_id"]      = n        }

        return await withCheckedContinuation { cont in
            LPRAPIClient.saveSighting(body, webView: webView) { ok, _ in
                cont.resume(returning: ok)
            }
        }
    }

    private func syncPost(_ item: OfflineQueueItem, path: String, webView: WKWebView) async -> Bool {
        var body: [String: Any] = [:]
        for (k, v) in item.payload { body[k] = v }
        return await LPRAPIClient.postAction(path: path, body: body, webView: webView)
    }

    private func fetchJSON(path: String, webView: WKWebView) async throws -> [String: Any] {
        return try await withCheckedThrowingContinuation { cont in
            LPRAPIClient.getJSON(path: path, webView: webView) { json in
                if let json {
                    cont.resume(returning: json)
                } else {
                    cont.resume(throwing: URLError(.badServerResponse))
                }
            }
        }
    }
}

// MARK: - Assigned follow-up lightweight summary

struct AssignedFollowupItem {
    let id:         Int
    let actionType: String
    let priority:   String
    let status:     String
    let lat:        Double?
    let lng:        Double?
}
