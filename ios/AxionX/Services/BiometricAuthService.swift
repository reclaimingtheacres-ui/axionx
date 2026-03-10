import Foundation
import LocalAuthentication
import WebKit

enum BiometricError: Error {
    case notAvailable
    case cancelled
    case failed
    case noSavedSession
}

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

    var settingsLabel: String {
        switch self {
        case .faceID:  return "Face ID"
        case .touchID: return "Touch ID"
        case .none:    return "Biometric"
        }
    }
}

private enum Prefs {
    static let optedInKey  = "biometric_opted_in"
    static let declinedKey = "biometric_declined"
}

enum BiometricAuthService {

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

    static var hasSavedToken: Bool {
        KeychainService.hasToken
    }

    static var isOptedIn: Bool {
        UserDefaults.standard.bool(forKey: Prefs.optedInKey)
    }

    static var hasDeclined: Bool {
        UserDefaults.standard.bool(forKey: Prefs.declinedKey)
    }

    static var shouldPromptOptIn: Bool {
        biometricType != .none && !isOptedIn && !hasDeclined
    }

    static func setOptedIn(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: Prefs.optedInKey)
        if value {
            UserDefaults.standard.set(false, forKey: Prefs.declinedKey)
        }
    }

    static func setDeclined(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: Prefs.declinedKey)
    }

    static func resetPreferences() {
        UserDefaults.standard.set(false, forKey: Prefs.optedInKey)
        UserDefaults.standard.set(false, forKey: Prefs.declinedKey)
    }

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

    static func saveToken(_ token: String) {
        KeychainService.saveToken(token)
        setOptedIn(true)
    }

    @discardableResult
    static func loadAndInjectSession() async -> Bool {
        guard let token = KeychainService.loadToken() else { return false }

        guard let url = URL(string: AppConfig.currentBaseURL + "/m/api/auth/token-login") else { return false }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")
        request.httpBody = try? JSONEncoder().encode(["token": token])

        let config = URLSessionConfiguration.ephemeral
        let session = URLSession(configuration: config)

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { return false }

            if http.statusCode == 200 {
                let headers = http.allHeaderFields as? [String: String] ?? [:]
                let cookies = HTTPCookie.cookies(withResponseHeaderFields: headers, for: url)
                await LoginService.injectCookies(cookies)
                return true
            }

            if http.statusCode == 401 {
                clearSession()
            }
            return false
        } catch {
            return false
        }
    }

    static func clearSession() {
        if let token = KeychainService.loadToken() {
            Task {
                await revokeTokenOnServer(token)
            }
        }
        KeychainService.deleteToken()
        KeychainService.delete()
    }

    static func disableBiometric() {
        clearSession()
        resetPreferences()
    }

    private static func revokeTokenOnServer(_ token: String) async {
        guard let url = URL(string: AppConfig.currentBaseURL + "/m/api/auth/revoke-token") else { return }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")
        request.httpBody = try? JSONEncoder().encode(["token": token])

        let config = URLSessionConfiguration.ephemeral
        let session = URLSession(configuration: config)
        _ = try? await session.data(for: request)
    }
}
