import Foundation
import CoreLocation

/// Manages iOS location permission for distance sorting, map positioning, and navigation.
/// The WebView's navigator.geolocation API will automatically prompt via the native iOS
/// location permission sheet when the page first calls getCurrentPosition() or watchPosition().
/// This manager provides a hook to pre-request or check permission status from native code.
final class LocationPermissionManager: NSObject {

    static let shared = LocationPermissionManager()

    private let locationManager = CLLocationManager()

    private override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    // MARK: - Public

    var authorizationStatus: CLAuthorizationStatus {
        locationManager.authorizationStatus
    }

    /// Request "When In Use" permission. Call this before presenting the map screen
    /// if you want to prime the permission prompt. WKWebView will also trigger this
    /// automatically when the page calls navigator.geolocation.
    func requestWhenInUseIfNeeded() {
        switch locationManager.authorizationStatus {
        case .notDetermined:
            locationManager.requestWhenInUseAuthorization()
        default:
            break
        }
        // "Always" permission is intentionally NOT requested in v1.
    }
}

// MARK: - CLLocationManagerDelegate

extension LocationPermissionManager: CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        // Location permission change is handled by the web layer (navigator.geolocation).
        // Future native GPS background mode can be triggered here.
        switch manager.authorizationStatus {
        case .authorizedWhenInUse:
            break // Web geolocation API is now available
        case .denied, .restricted:
            break // Web layer shows "Location off" banner
        default:
            break
        }
    }
}
