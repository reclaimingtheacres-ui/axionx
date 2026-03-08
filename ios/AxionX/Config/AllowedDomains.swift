import Foundation

/// Controls which URLs stay inside the WebView and which open externally.
/// The set of trusted hosts is built at runtime from the production domains
/// plus whatever host AppConfig.currentBaseURL resolves to, so staging builds
/// automatically trust the Replit dev domain without any manual changes here.
enum AllowedDomains {

    // ── Trusted hosts (always stay inside WebView) ────────────────────────────
    static let trusted: Set<String> = {
        var domains: Set<String> = [
            "www.axionx.com.au",
            "axionx.com.au",
        ]
        // Automatically add the active environment's host so staging builds
        // (Replit dev URL) work without any code changes.
        if let host = URL(string: AppConfig.currentBaseURL)?.host?.lowercased() {
            domains.insert(host)
        }
        return domains
    }()

    // ── Native URL schemes (open in system app) ───────────────────────────────
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
