import CoreLocation
import Foundation
import UIKit

// MARK: - Agent Location Service
//
// Manages three distinct tracking modes driven by the agent's field status.
// No customer, finance, or internal file data is included in any location payload.
// Only: coordinates, accuracy_m, battery state, context (foreground/background), source, and timestamp.

final class AgentLocationService: NSObject {

    static let shared = AgentLocationService()

    // MARK: - Private state

    private let manager: CLLocationManager = {
        let m = CLLocationManager()
        m.desiredAccuracy            = kCLLocationAccuracyNearestTenMeters
        m.distanceFilter             = 100           // metres — coarse filter when available
        m.pausesLocationUpdatesAutomatically = false
        m.allowsBackgroundLocationUpdates   = true
        return m
    }()

    private(set) var currentStatus: FieldStatus = .offDuty
    private var activeJobTimer: Timer?
    static let activeJobDuration: TimeInterval = 30 * 60     // 30 minutes

    private override init() {
        super.init()
        manager.delegate = self
        UIDevice.current.isBatteryMonitoringEnabled = true
    }

    // MARK: - Mode switching

    /// Apply a new field status. Safe to call from any thread.
    func apply(_ status: FieldStatus) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.currentStatus = status
            self.stopAll()
            switch status {
            case .offDuty:
                break
            case .available:
                self.ensureAlwaysPermission()
                self.manager.startMonitoringSignificantLocationChanges()
            case .activeJob:
                self.ensureAlwaysPermission()
                self.manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
                self.manager.distanceFilter  = 50
                self.manager.startUpdatingLocation()
                self.scheduleActiveJobTimeout()
            }
        }
    }

    // MARK: - Permission helper

    func ensureAlwaysPermission() {
        let status = manager.authorizationStatus
        if status == .notDetermined || status == .authorizedWhenInUse {
            manager.requestAlwaysAuthorization()
        }
    }

    // MARK: - Private helpers

    private func stopAll() {
        manager.stopUpdatingLocation()
        manager.stopMonitoringSignificantLocationChanges()
        activeJobTimer?.invalidate()
        activeJobTimer = nil
    }

    private func scheduleActiveJobTimeout() {
        activeJobTimer?.invalidate()
        activeJobTimer = Timer.scheduledTimer(
            withTimeInterval: Self.activeJobDuration,
            repeats: false
        ) { _ in
            Task { @MainActor in
                FieldStatusManager.shared.downgradeActiveJob()
            }
        }
    }

    // MARK: - Location delivery

    fileprivate func deliver(_ location: CLLocation, source: String) {
        let batState: String
        switch UIDevice.current.batteryState {
        case .charging:   batState = "charging"
        case .full:       batState = "full"
        case .unplugged:  batState = "unplugged"
        default:          batState = "unknown"
        }

        let inForeground = UIApplication.shared.applicationState == .active
        let context      = inForeground ? "foreground" : "background"

        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        let capturedAt = iso.string(from: location.timestamp)

        Task { @MainActor in
            SyncManager.shared.enqueueLocationPing(
                lat:        location.coordinate.latitude,
                lng:        location.coordinate.longitude,
                accuracy:   location.horizontalAccuracy,
                battery:    batState,
                context:    context,
                source:     source,
                capturedAt: capturedAt
            )
        }
    }
}

// MARK: - CLLocationManagerDelegate

extension AgentLocationService: CLLocationManagerDelegate {

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        let src = currentStatus == .activeJob ? "active_job" : "foreground"
        deliver(loc, source: src)
    }

    func locationManager(
        _ manager: CLLocationManager,
        didFailWithError error: Error
    ) {
        // Non-critical — individual fixes can fail silently
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let s = manager.authorizationStatus
        if s == .authorizedAlways || s == .authorizedWhenInUse {
            // Re-apply current mode now that we have permission
            apply(currentStatus)
        }
    }
}
