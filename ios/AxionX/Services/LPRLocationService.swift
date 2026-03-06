import CoreLocation
import Foundation

/// One-shot GPS fix for attaching coordinates to LPR sightings.
/// Reuses the permission state already managed by LocationPermissionHelper.
final class LPRLocationService: NSObject {

    static let shared = LPRLocationService()

    private let manager: CLLocationManager = {
        let m = CLLocationManager()
        m.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        return m
    }()

    private var pending: [(CLLocation?) -> Void] = []
    private var isRequesting = false

    private override init() {
        super.init()
        manager.delegate = self
    }

    /// Request the current location once.
    /// Calls `completion` on the main thread with a location or nil.
    func currentLocation(completion: @escaping (CLLocation?) -> Void) {
        let status = manager.authorizationStatus
        guard status == .authorizedWhenInUse || status == .authorizedAlways else {
            completion(nil)
            return
        }
        pending.append(completion)
        guard !isRequesting else { return }
        isRequesting = true
        manager.requestLocation()
    }
}

// MARK: - CLLocationManagerDelegate

extension LPRLocationService: CLLocationManagerDelegate {

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        isRequesting = false
        let loc = locations.last
        let handlers = pending
        pending.removeAll()
        DispatchQueue.main.async { handlers.forEach { $0(loc) } }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        isRequesting = false
        let handlers = pending
        pending.removeAll()
        DispatchQueue.main.async { handlers.forEach { $0(nil) } }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        // no-op — permission changes are handled by LocationPermissionHelper
    }
}
