import Foundation
import LocalAuthentication
import WebKit

// MARK: - Stored cookie model

/// Codable representation of an HTTPCookie.
/// Stores only the fields needed to reconstruct it on the next launch.
private struct StoredCookie: Codable {
    let name:       String
    let value:      String
    let domain:     String
    let path:       String
    let isSecure:   Bool
    let expiresDate: Date?

    init(from cookie: HTTPCookie) {
        name        = cookie.name
        value       = cookie.value
        domain      = cookie.domain
        path        = cookie.path
        isSecure    = cookie.isSecure
        expiresDate = cookie.expiresDate
    }

    var asHTTPCookie: HTTPCookie? {
        var props: [HTTPCookiePropertyKey: Any] = [
            .name:   name,
            .value:  value,
            .domain: domain,
            .path:   path,
        ]
        if isSecure    { props[.secure]  = "TRUE" }
        if let expires = expiresDate { props[.expires] = expires }
        return HTTPCookie(properties: props)
    }

    var isExpired: Bool {
        guard let expires = expiresDate else { return false }
        return expires <= Date()
    }
}

// MARK: - Biometric errors

enum BiometricError: Error {
    case notAvailable
    case cancelled
    case failed
    case noSavedSession
}

// MARK: - Biometric type

enum BiometricType {
    case none, faceID, touchID

    var systemImageName: String {
        switch self {
        case .faceID:  return "faceid"
        case .touchID: return "touchid"
        case .none:    return ""
        }
    }

    var label: String {
        switch self {
        case .faceID:  return "Use Face ID"
        case .touchID: return "Use Touch ID"
        case .none:    return ""
        }
    }
}

// MARK: - Service

enum BiometricAuthService {

    // MARK: - Device capability

    static var biometricType: BiometricType {
        let ctx = LAContext()
        var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &err) else {
            return .none
        }
        switch ctx.biometryType {
        case .faceID:  return .faceID
        case .touchID: return .touchID
        default:       return .none
        }
    }

    // MARK: - Session availability

    static var hasSavedSession: Bool {
        guard let data = KeychainService.load() else { return false }
        guard let stored = try? JSONDecoder().decode(StoredCookie.self, from: data) else { return false }
        return !stored.isExpired
    }

    // MARK: - Biometric prompt

    /// Presents the Face ID / Touch ID prompt.
    /// Throws `BiometricError.cancelled` when the user dismisses it.
    /// Throws `BiometricError.failed` for a scan mismatch or lockout.
    static func authenticate(reason: String) async throws {
        let ctx = LAContext()
        var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &err) else {
            throw BiometricError.notAvailable
        }

        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            ctx.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                               localizedReason: reason) { success, error in
                if success {
                    cont.resume()
                } else if let laErr = error as? LAError, laErr.code == .userCancel {
                    cont.resume(throwing: BiometricError.cancelled)
                } else {
                    cont.resume(throwing: BiometricError.failed)
                }
            }
        }
    }

    // MARK: - Session persistence

    /// Saves the Flask session cookie to Keychain.
    /// Called after every successful manual login so biometric can be used next time.
    static func saveSession(from cookies: [HTTPCookie]) {
        guard let sessionCookie = cookies.first(where: { $0.name == "session" }) else { return }
        guard let data = try? JSONEncoder().encode(StoredCookie(from: sessionCookie)) else { return }
        KeychainService.save(data)
    }

    /// Injects the Keychain-stored session cookie into WKWebsiteDataStore.
    /// Returns `true` if a valid, non-expired cookie was found and injected.
    @discardableResult
    static func loadAndInjectSession() async -> Bool {
        guard let data   = KeychainService.load()                                    else { return false }
        guard let stored = try? JSONDecoder().decode(StoredCookie.self, from: data)  else { return false }
        guard !stored.isExpired                                                       else {
            KeychainService.delete()
            return false
        }
        guard let cookie = stored.asHTTPCookie else { return false }

        let store = WKWebsiteDataStore.default().httpCookieStore
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            store.setCookie(cookie) { cont.resume() }
        }
        return true
    }

    /// Removes the saved session from Keychain (e.g., on sign-out or auth failure).
    static func clearSession() {
        KeychainService.delete()
    }
}
