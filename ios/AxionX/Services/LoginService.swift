import Foundation
import WebKit

enum LoginError: Error {
    case invalidCredentials
    case networkError(Error)
    case unknown
}

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

struct LoginResult {
    let cookies: [HTTPCookie]
    let authToken: String?
}

enum LoginService {

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
        guard http.statusCode == 302 else { throw LoginError.invalidCredentials }

        let headers = http.allHeaderFields as? [String: String] ?? [:]
        let cookies = HTTPCookie.cookies(withResponseHeaderFields: headers, for: url)
        return cookies
    }

    static func loginAndPersist(email: String, password: String, requestToken: Bool = false) async throws -> LoginResult {
        let cookies = try await login(email: email, password: password)
        await injectCookies(cookies)

        var authToken: String? = nil
        if requestToken {
            await revokeExistingTokens(cookies: cookies)
            authToken = await createAuthToken(cookies: cookies)
        }

        return LoginResult(cookies: cookies, authToken: authToken)
    }

    static func injectCookies(_ cookies: [HTTPCookie]) async {
        let store = WKWebsiteDataStore.default().httpCookieStore
        for cookie in cookies {
            await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
                store.setCookie(cookie) { cont.resume() }
            }
        }
    }

    static func hasValidSession() async -> Bool {
        await withCheckedContinuation { cont in
            WKWebsiteDataStore.default().httpCookieStore.getAllCookies { cookies in
                let valid = cookies.contains {
                    $0.name == "session" &&
                    ($0.expiresDate == nil || $0.expiresDate! > Date())
                }
                cont.resume(returning: valid)
            }
        }
    }

    static func revokeExistingTokens(cookies: [HTTPCookie]) async {
        guard let url = URL(string: AppConfig.currentBaseURL + "/m/api/auth/revoke-all-tokens") else { return }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")

        let cookieHeaders = HTTPCookie.requestHeaderFields(with: cookies)
        for (key, value) in cookieHeaders {
            request.setValue(value, forHTTPHeaderField: key)
        }

        let config = URLSessionConfiguration.ephemeral
        let session = URLSession(configuration: config)
        _ = try? await session.data(for: request)
    }

    static func revokeToken(_ token: String) async {
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

    private static func createAuthToken(cookies: [HTTPCookie]) async -> String? {
        guard let url = URL(string: AppConfig.currentBaseURL + "/m/api/auth/create-token") else { return nil }

        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")

        let deviceName = UIDevice.current.name
        request.httpBody = try? JSONEncoder().encode(["device_name": deviceName])

        let cookieHeaders = HTTPCookie.requestHeaderFields(with: cookies)
        for (key, value) in cookieHeaders {
            request.setValue(value, forHTTPHeaderField: key)
        }

        let config = URLSessionConfiguration.ephemeral
        let session = URLSession(configuration: config)

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return nil }

            struct TokenResponse: Decodable {
                let token: String
                let expires_at: String
            }
            let decoded = try JSONDecoder().decode(TokenResponse.self, from: data)
            return decoded.token
        } catch {
            return nil
        }
    }
}
