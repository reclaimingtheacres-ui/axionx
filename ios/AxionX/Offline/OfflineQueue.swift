import Foundation

// MARK: - Queue item status

enum QueueItemStatus: String, Codable {
    case pending
    case syncing
    case success
    case failed
}

// MARK: - Queue item (no sensitive customer / finance data)
//
// Stores only the fields that the native LPR layer is already authorised to
// handle: plate number, result type, search method, GPS, agent notes, and
// action-routing keys.  Customer names, addresses, arrears, and contract data
// are never written here.

struct OfflineQueueItem: Codable, Identifiable {
    var id: String { clientActionId }
    let clientActionId: String   // UUID — used as idempotency key on server
    let actionType: String       // "save_sighting" | "register_device" | "mark_notifications_read"
    let payload: [String: String]
    let createdAt: Date
    var retryCount: Int
    var lastError: String?
    var status: QueueItemStatus

    init(clientActionId: String = UUID().uuidString,
         actionType: String,
         payload: [String: String]) {
        self.clientActionId = clientActionId
        self.actionType     = actionType
        self.payload        = payload
        self.createdAt      = Date()
        self.retryCount     = 0
        self.lastError      = nil
        self.status         = .pending
    }

    var actionLabel: String {
        switch actionType {
        case "save_sighting":            return "Save Sighting"
        case "register_device":          return "Device Registration"
        case "mark_notifications_read":  return "Mark Alerts Read"
        case "location_ping":            return "Location Ping"
        default:                         return actionType.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    var plateLabel: String? {
        payload["registration_raw"]
    }
}

// MARK: - Thread-safe persistent queue (UserDefaults-backed)

final class OfflineQueue {

    static let shared = OfflineQueue()

    private let udKey = "com.axionx.lpr_offline_queue_v1"
    private let lock  = NSLock()
    private var items: [OfflineQueueItem] = []

    private init() { load() }

    // MARK: - Accessors

    var allItems: [OfflineQueueItem] {
        lock.lock(); defer { lock.unlock() }
        return items
    }

    var pendingItems: [OfflineQueueItem] {
        lock.lock(); defer { lock.unlock() }
        return items.filter { $0.status == .pending || $0.status == .syncing }
    }

    var failedItems: [OfflineQueueItem] {
        lock.lock(); defer { lock.unlock() }
        return items.filter { $0.status == .failed }
    }

    var recentSuccessItems: [OfflineQueueItem] {
        lock.lock(); defer { lock.unlock() }
        return Array(items.filter { $0.status == .success }.suffix(10).reversed())
    }

    var pendingCount: Int { pendingItems.count }
    var failedCount:  Int { failedItems.count  }

    // MARK: - Mutations

    func enqueue(_ item: OfflineQueueItem) {
        lock.lock()
        guard !items.contains(where: { $0.clientActionId == item.clientActionId }) else {
            lock.unlock(); return
        }
        items.append(item)
        lock.unlock()
        save()
    }

    func markSyncing(_ id: String) {
        mutate(id) { $0.status = .syncing }
    }

    func markSuccess(_ id: String) {
        mutate(id) {
            $0.status    = .success
            $0.lastError = nil
        }
        pruneOldSuccesses()
        save()
    }

    func markFailed(_ id: String, error: String) {
        mutate(id) {
            $0.status    = .failed
            $0.lastError = error
            $0.retryCount += 1
        }
    }

    func resetToPending(_ id: String) {
        mutate(id) { $0.status = .pending }
    }

    func remove(_ id: String) {
        lock.lock()
        items.removeAll { $0.clientActionId == id }
        lock.unlock()
        save()
    }

    // MARK: - Private helpers

    private func mutate(_ id: String, block: (inout OfflineQueueItem) -> Void) {
        lock.lock()
        guard let idx = items.firstIndex(where: { $0.clientActionId == id }) else {
            lock.unlock(); return
        }
        block(&items[idx])
        lock.unlock()
        save()
    }

    private func pruneOldSuccesses() {
        lock.lock()
        let successes = items.filter { $0.status == .success }
        if successes.count > 20 {
            let drop = Set(successes.prefix(successes.count - 20).map { $0.clientActionId })
            items.removeAll { drop.contains($0.clientActionId) }
        }
        lock.unlock()
    }

    private func load() {
        guard let data    = UserDefaults.standard.data(forKey: udKey),
              let decoded = try? JSONDecoder().decode([OfflineQueueItem].self, from: data)
        else { return }
        items = decoded.filter { $0.status != .success }
        for i in items.indices where items[i].status == .syncing {
            items[i].status = .pending   // reset interrupted syncs on restart
        }
    }

    private func save() {
        lock.lock()
        let snapshot = items
        lock.unlock()
        if let data = try? JSONEncoder().encode(snapshot) {
            UserDefaults.standard.set(data, forKey: udKey)
        }
    }
}
