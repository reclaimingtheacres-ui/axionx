import Foundation
import Security

/// A minimal Keychain wrapper for storing the AxionX session cookie securely.
/// Stored under kSecClassGenericPassword with device-only, when-unlocked protection.
enum KeychainService {

    private static let service = "com.axionx.app"
    private static let account = "session-cookie"

    // MARK: - Public API

    static func save(_ data: Data) {
        // Delete any existing item first
        delete()

        let query: [CFString: Any] = [
            kSecClass:                kSecClassGenericPassword,
            kSecAttrService:          service,
            kSecAttrAccount:          account,
            kSecValueData:            data,
            // Accessible only on this device, when the device is unlocked.
            // Using ThisDeviceOnly prevents migration to a new device via iCloud backup.
            kSecAttrAccessible:       kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    static func load() -> Data? {
        let query: [CFString: Any] = [
            kSecClass:       kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecReturnData:  true,
            kSecMatchLimit:  kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess else { return nil }
        return result as? Data
    }

    static func delete() {
        let query: [CFString: Any] = [
            kSecClass:       kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    static var hasItem: Bool { load() != nil }
}
