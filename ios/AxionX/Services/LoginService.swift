import Foundation
import WebKit

// MARK: - Login errors

enum LoginError: Error {
    case invalidCredentials
    case networkError(Error)
    case unknown
}

// MARK: - Redirect-blocking delegate

private final class NoRedirectDelegate: NSObject, URLSessionTaskDelegate {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}

// MARK: - Login service

enum LoginService {

    /// POST credentials to /m/login.
    /// Flask returns 302 on success, 200 on failure.
    /// Stops before following the redirect so Set-Cookie can be read.
    static func login(email: String, password: String) async throws -> [HTTPCookie] {
        guard let url = URL(string: AppConfig.currentBaseURL + "/m/login") else {
            throw LoginError.unknown
        }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")

        let safeEmail    = email.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let safePassword = password.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        request.httpBody = "email=\(safeEmail)&password=\(safePassword)".data(using: .utf8)

        let config  = URLSessionConfiguration.ephemeral
        let session = URLSession(configuration: config, delegate: NoRedirectDelegate(), delegateQueue: nil)

        let (_, response): (Data, URLResponse)
        do {
            (_, response) = try await session.data(for: request)
        } catch {
            throw LoginError.networkError(error)
        }

        guard let http = response as? HTTPURLResponse else { throw LoginError.unknown }

        // Flask returns HTTP 302 on success, 200 (re-rendered page) on failure
        guard http.statusCode == 302 else { throw LoginError.invalidCredentials }

        let headers = http.allHeaderFields as? [String: String] ?? [:]
        let cookies = HTTPCookie.cookies(withResponseHeaderFields: headers, for: url)
        return cookies
    }

    /// Inject cookies into the WKWebView's persistent data store so subsequent
    /// web requests made by the WebView are already authenticated.
    static func injectCookies(_ cookies: [HTTPCookie]) async {
        let store = WKWebsiteDataStore.default().httpCookieStore
        for cookie in cookies {
            await store.set(cookie)
        }
    }

    /// Returns true if a non-expired session cookie already exists in the
    /// WKWebView's persistent data store from a previous login.
    static func hasValidSession() async -> Bool {
        let cookies = await WKWebsiteDataStore.default().httpCookieStore.allCookies()
        return cookies.contains {
            $0.name == "session" &&
            ($0.expiresDate == nil || $0.expiresDate! > Date())
        }
    }
}

// MARK: - WKHTTPCookieStore async helpers

private extension WKHTTPCookieStore {

    func allCookies() async -> [HTTPCookie] {
        await withCheckedContinuation { cont in
            getAllCookies { cont.resume(returning: $0) }
        }
    }

    func set(_ cookie: HTTPCookie) async {
        await withCheckedContinuation { cont in
            setCookie(cookie) { cont.resume() }
        }
    }
}
