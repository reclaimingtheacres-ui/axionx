import Foundation

/// Controls which URLs stay inside the WebView and which open externally.
enum AllowedDomains {

    // ── Trusted hosts (load inside WebView) ──────────────────────────────────
    static let trusted: Set<String> = [
        "www.axionx.com.au",
        "axionx.com.au",
        // Add staging or dev domains here as needed:
        // "your-project.replit.app",
    ]

    // ── Native URL schemes (open in system app) ──────────────────────────────
    private static let nativeSchemes: Set<String> = ["tel", "sms", "facetime", "facetime-audio"]

    // ── Map hosts (open in Apple Maps) ───────────────────────────────────────
    private static let mapHosts: Set<String> = ["maps.apple.com", "maps.google.com"]

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// True if the URL belongs to a trusted AxionX host.
    static func isTrusted(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return trusted.contains(host) || trusted.contains("www.\(host)")
    }

    /// True if the URL should open in a native system app (Phone, Messages, etc).
    static func isNativeScheme(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased() else { return false }
        return nativeSchemes.contains(scheme)
    }

    /// True if the URL should open in Apple Maps.
    static func isMapsURL(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return mapHosts.contains(host)
    }

    /// True if the URL is an HTTP/HTTPS link to an external (non-trusted) site.
    static func isExternalWeb(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https" else { return false }
        return !isTrusted(url)
    }
}
