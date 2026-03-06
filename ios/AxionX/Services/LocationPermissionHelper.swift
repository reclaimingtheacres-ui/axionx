import CoreLocation
import Foundation

/// Helper for iOS location permission handling.
/// v1 requests "When In Use" only — "Always" is intentionally deferred.
///
/// Important: The WebView's navigator.geolocation API automatically triggers
/// the iOS location permission prompt when the page calls getCurrentPosition().
/// This helper exists for native-code callers and future background GPS support.
final class LocationPermissionHelper: NSObject {

    static let shared = LocationPermissionHelper()

    private let manager = CLLocationManager()

    private override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    // MARK: - Public API

    var status: CLAuthorizationStatus { manager.authorizationStatus }

    /// Request "When In Use" permission if not yet determined.
    /// Safe to call multiple times — no-ops if already granted/denied.
    func requestWhenInUseIfNeeded() {
        if manager.authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        }
        // "Always" permission is NOT requested in v1.
    }

    var isAuthorized: Bool {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways: return true
        default: return false
        }
    }
}

// MARK: - CLLocationManagerDelegate

extension LocationPermissionHelper: CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        // Authorization changes are handled by the web layer (navigator.geolocation).
        // Future: trigger background GPS session here when "Always" is added in v2.
    }
}
