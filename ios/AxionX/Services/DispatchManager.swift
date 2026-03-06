import CoreLocation
import Combine
import Foundation
import WebKit

// MARK: - Dispatch Summary models
//
// No customer, finance, or internal file data is stored here.
// Only operational fields: follow-up action type, priority, status,
// sighting coordinates, and plate registration.

struct DispatchSummary: Identifiable, Codable {
    let id:         Int
    let actionType: String
    let priority:   String
    var status:     String
    let dueAt:      String
    let officeNote: String
    let sighting:   SightingLocation

    struct SightingLocation: Codable {
        let id:          Int
        let registration: String
        let resultType:  String
        let latitude:    Double?
        let longitude:   Double?
        let sightingAt:  String
    }

    var location: CLLocation? {
        guard let lat = sighting.latitude, let lng = sighting.longitude else { return nil }
        return CLLocation(latitude: lat, longitude: lng)
    }

    var priorityColor: (red: Double, green: Double, blue: Double) {
        switch priority {
        case "urgent": return (0.86, 0.10, 0.10)
        case "high":   return (0.85, 0.47, 0.05)
        case "low":    return (0.09, 0.63, 0.29)
        default:       return (0.15, 0.50, 0.95)
        }
    }

    var actionLabel: String {
        switch actionType {
        case "notify":              return "Notify Office"
        case "field_locate":        return "Field Locate"
        case "voluntary_surrender": return "Voluntary Surrender"
        case "repossess":           return "Repossess"
        case "investigate":         return "Investigate"
        default:
            return actionType
                .replacingOccurrences(of: "_", with: " ")
                .capitalized
        }
    }
}

// MARK: - Dispatch Manager

/// Singleton that owns the native dispatch workflow for an accepted LPR follow-up.
/// Drives status transitions, region monitoring (near_target), and Apple Maps navigation.
/// No customer or finance data is stored or exposed.

@MainActor
final class DispatchManager: NSObject, ObservableObject {

    static let shared = DispatchManager()

    // MARK: - Published state

    @Published var activeDispatch: DispatchSummary? = nil
    @Published var isLoadingDispatch = false

    // MARK: - CLLocationManager for near_target region monitoring

    private let regionManager: CLLocationManager = {
        let m = CLLocationManager()
        m.desiredAccuracy = kCLLocationAccuracyHundredMeters
        return m
    }()

    private var monitoredFollowupId: Int? = nil
    private static let nearTargetRadius: CLLocationDistance = 150.0
    private static let regionIdentifierPrefix = "axion.dispatch."

    private override init() {
        super.init()
        regionManager.delegate = self
    }

    // MARK: - Load follow-up detail

    func fetchAndActivate(followupId: Int, webView: WKWebView) async {
        guard !isLoadingDispatch else { return }
        isLoadingDispatch = true
        defer { isLoadingDispatch = false }

        do {
            let summary = try await loadFollowup(id: followupId, wv: webView)
            activeDispatch = summary
            if summary.priority == "urgent" || summary.priority == "high" {
                startRegionMonitoring(for: summary)
            }
        } catch {
            // Non-fatal — dispatch detail fetch fails silently
        }
    }

    func dismissDispatch() {
        if let dispatch = activeDispatch {
            stopRegionMonitoring(id: dispatch.id)
        }
        activeDispatch = nil
    }

    // MARK: - Status transitions

    /// Update follow-up status both locally and through the offline queue.
    func updateStatus(_ newStatus: String) {
        guard var dispatch = activeDispatch else { return }
        dispatch.status = newStatus
        activeDispatch  = dispatch

        SyncManager.shared.enqueueFollowupStatusUpdate(
            followupId: dispatch.id,
            status:     newStatus
        )

        if newStatus == "completed" || newStatus == "cancelled" {
            stopRegionMonitoring(id: dispatch.id)
            // Auto-dismiss after a short delay so the UI can acknowledge
            Task {
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                activeDispatch = nil
            }
        }
    }

    // MARK: - Apple Maps deep link

    /// Open Apple Maps for turn-by-turn navigation to the sighting location.
    /// No customer address is passed — only raw coordinates.
    func openInMaps() {
        guard let loc = activeDispatch?.location else { return }
        let lat = loc.coordinate.latitude
        let lng = loc.coordinate.longitude
        let label = "LPR Sighting"
        let encoded = label.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? label
        if let url = URL(string: "maps://?daddr=\(lat),\(lng)&dirflg=d&t=m&q=\(encoded)") {
            UIApplication.shared.open(url)
        }
    }

    // MARK: - Region monitoring (near_target)

    private func startRegionMonitoring(for dispatch: DispatchSummary) {
        guard CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self),
              let loc = dispatch.location else { return }
        stopRegionMonitoring(id: dispatch.id)

        let identifier = Self.regionIdentifierPrefix + "\(dispatch.id)"
        let region = CLCircularRegion(
            center: loc.coordinate,
            radius: Self.nearTargetRadius,
            identifier: identifier
        )
        region.notifyOnEntry = true
        region.notifyOnExit  = false
        regionManager.startMonitoring(for: region)
        monitoredFollowupId = dispatch.id
    }

    private func stopRegionMonitoring(id: Int) {
        let identifier = Self.regionIdentifierPrefix + "\(id)"
        for region in regionManager.monitoredRegions
        where region.identifier == identifier {
            regionManager.stopMonitoring(for: region)
        }
        if monitoredFollowupId == id {
            monitoredFollowupId = nil
        }
    }

    // MARK: - API fetch (no customer data returned)

    private func loadFollowup(id: Int, wv: WKWebView) async throws -> DispatchSummary {
        return try await withCheckedThrowingContinuation { cont in
            LPRAPIClient.getJSON(path: "/m/api/lpr/followup/\(id)",
                                 webView: wv) { json in
                guard let json else {
                    cont.resume(throwing: URLError(.badServerResponse))
                    return
                }
                guard let sightingDict = json["sighting"] as? [String: Any] else {
                    cont.resume(throwing: URLError(.cannotParseResponse))
                    return
                }
                let summary = DispatchSummary(
                    id:         json["id"]          as? Int    ?? id,
                    actionType: json["action_type"] as? String ?? "",
                    priority:   json["priority"]    as? String ?? "normal",
                    status:     json["status"]       as? String ?? "assigned",
                    dueAt:      json["due_at"]       as? String ?? "",
                    officeNote: json["office_note"]  as? String ?? "",
                    sighting: DispatchSummary.SightingLocation(
                        id:           sightingDict["id"]           as? Int    ?? 0,
                        registration: sightingDict["registration"] as? String ?? "",
                        resultType:   sightingDict["result_type"]  as? String ?? "",
                        latitude:     sightingDict["latitude"]     as? Double,
                        longitude:    sightingDict["longitude"]    as? Double,
                        sightingAt:   sightingDict["sighting_at"]  as? String ?? ""
                    )
                )
                cont.resume(returning: summary)
            }
        }
    }
}

// MARK: - CLLocationManagerDelegate (region entry → near_target)

extension DispatchManager: CLLocationManagerDelegate {

    nonisolated func locationManager(
        _ manager: CLLocationManager,
        didEnterRegion region: CLRegion
    ) {
        guard region.identifier.hasPrefix(Self.regionIdentifierPrefix) else { return }
        let suffix = region.identifier.dropFirst(Self.regionIdentifierPrefix.count)
        guard let followupId = Int(suffix) else { return }

        Task { @MainActor [weak self] in
            guard let self,
                  let dispatch = self.activeDispatch,
                  dispatch.id == followupId,
                  dispatch.status == "en_route" else { return }
            self.updateStatus("near_target")
        }
    }

    nonisolated func locationManager(
        _ manager: CLLocationManager,
        monitoringDidFailFor region: CLRegion?,
        withError error: Error
    ) {}
}
