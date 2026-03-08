import Foundation

/// Central build-time configuration.
///
/// The server URL and environment name are injected at compile time via xcconfig
/// files (Staging.xcconfig / Production.xcconfig) → Info.plist, so they cannot
/// be changed at runtime. Switching environments requires a separate build.
///
/// Configurations:
///   Staging    → AXIONX_BASE_URL = Replit dev URL  (separate dev database)
///   Production → AXIONX_BASE_URL = www.axionx.com.au  (LIVE DATA)
///
/// When no xcconfig is assigned (direct simulator run from Xcode):
///   Debug → http://localhost:5000
///   Release → www.axionx.com.au  (safe fallback; never archives without xcconfig)
enum AppConfig {

    // ── Environment (read from xcconfig → Info.plist) ────────────────────────
    // Never hard-coded here. Changing environments = new archive.

    static let currentBaseURL: String = {
        if let url = Bundle.main.infoDictionary?["AXIONX_BASE_URL"] as? String,
           !url.isEmpty,
           !url.hasPrefix("$(")  // unexpanded xcconfig variable = xcconfig not assigned
        {
            return url
        }
        // Fallback for direct Xcode runs without an xcconfig assigned
        #if DEBUG
        return "http://localhost:5000"
        #else
        return "https://www.axionx.com.au"
        #endif
    }()

    static let environmentName: String = {
        let v = Bundle.main.infoDictionary?["AXIONX_ENV_NAME"] as? String ?? ""
        if v.isEmpty || v.hasPrefix("$(") {
            #if DEBUG
            return "Local"
            #else
            return "Production"
            #endif
        }
        return v
    }()

    /// True only when the build targets the live production server.
    /// Every write in a production build touches real data.
    static var isProduction: Bool { environmentName == "Production" }

    /// True when the build targets the Replit dev (staging) environment.
    static var isStaging: Bool { environmentName == "Staging" }

    // ── Entry point ──────────────────────────────────────────────────────────
    static let mobileEntryPath = "/m/schedule/today"

    static var entryURL: URL {
        guard let url = URL(string: currentBaseURL + mobileEntryPath) else {
            fatalError("AppConfig.entryURL is invalid — check currentBaseURL and mobileEntryPath")
        }
        return url
    }

    // ── App identity ──────────────────────────────────────────────────────────
    static let displayName   = "AxionX"
    static let userAgent     = "AxionXiOS/1.0"
    static let splashDelay: TimeInterval = 1.4

    // ── Offline message ───────────────────────────────────────────────────────
    static let offlineMessage = "AxionX is currently unavailable.\nPlease check your internet connection and try again."
}
