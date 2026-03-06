import Foundation

/// Central build-time configuration. Edit this file to switch environments.
/// Debug builds point to dev/staging; Release builds point to production.
enum AppConfig {

    // ── Environment URLs ────────────────────────────────────────────────────
    #if DEBUG
    /// Replace with your Replit preview URL (no trailing slash).
    static let debugBaseURL   = "https://YOUR-REPLIT-PROJECT.replit.app"
    static let currentBaseURL = debugBaseURL
    #else
    static let releaseBaseURL = "https://www.axionx.com.au"
    static let currentBaseURL = releaseBaseURL
    #endif

    // ── Entry point ─────────────────────────────────────────────────────────
    static let mobileEntryPath = "/m/login"

    static var entryURL: URL {
        guard let url = URL(string: currentBaseURL + mobileEntryPath) else {
            fatalError("AppConfig.entryURL is invalid — check currentBaseURL")
        }
        return url
    }

    // ── App identity ─────────────────────────────────────────────────────────
    static let displayName   = "AxionX"
    static let userAgent     = "AxionXiOS/1.0"
    static let splashDelay: TimeInterval = 1.4   // seconds to show splash before loading

    // ── Offline message ───────────────────────────────────────────────────────
    static let offlineMessage = "AxionX is currently unavailable.\nPlease check your internet connection and try again."
}
