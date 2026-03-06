import Foundation

enum AppConfig {

    // ── Build-time URL selection ──────────────────────────────────────────
    // Debug builds load from the Replit dev URL or staging.
    // Release / TestFlight / App Store builds load from production.
    #if DEBUG
    static let startURL = URL(string: "https://YOUR-REPLIT-DEV-URL.replit.app/m/login")!
    #else
    static let startURL = URL(string: "https://www.axionx.com.au/m/login")!
    #endif

    // ── Hosts that are allowed to navigate inside the WebView ─────────────
    // Everything else opens in Safari.
    static let allowedHosts: Set<String> = [
        "www.axionx.com.au",
        "axionx.com.au",
        // Add your Replit dev domain here if needed during development:
        // "your-replit-project.replit.app",
    ]

    // ── URL schemes handled natively ──────────────────────────────────────
    // tel: → Phone   sms: → Messages   maps:/http://maps.apple.com/ → Maps
    static let nativeSchemes: Set<String> = ["tel", "sms", "facetime", "facetime-audio"]
    static let mapsHosts: Set<String>     = ["maps.apple.com", "maps.google.com"]

    // ── App identity ──────────────────────────────────────────────────────
    static let displayName = "AxionX"
    static let offlineMessage = "AxionX is currently unavailable.\nPlease check your internet connection and try again."
}
