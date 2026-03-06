import Foundation
import UIKit
import UserNotifications

// MARK: - Push Notification Service
//
// Handles:
//   1. Requesting UNUserNotification permission from the user
//   2. Registering with APNs via UIApplication.registerForRemoteNotifications()
//   3. Uploading the device token to the AxionX backend for server-side delivery
//
// AxionXApp.swift activates this once the user is in the authenticated WebView shell.

@MainActor
final class PushNotificationService: NSObject {

    static let shared = PushNotificationService()
    private override init() { super.init() }

    // MARK: - Request permission + register

    func requestPermissionAndRegister() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound, .badge]
        ) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    // MARK: - Upload token to AxionX backend

    func uploadToken(_ deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()

        guard let url = URL(string: AppConfig.currentBaseURL + "/m/api/device/register") else {
            return
        }

        var request        = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")

        let body: [String: Any] = ["token": tokenString, "platform": "ios"]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { _, _, _ in }.resume()
    }

    // MARK: - Unread count badge (polled after login)

    func refreshUnreadBadge() {
        guard let url = URL(
            string: AppConfig.currentBaseURL + "/m/api/lpr/notifications/unread-count"
        ) else { return }

        var request = URLRequest(url: url)
        request.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")

        URLSession.shared.dataTask(with: request) { data, _, _ in
            guard let data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let count = json["count"] as? Int else { return }
            DispatchQueue.main.async {
                UIApplication.shared.applicationIconBadgeNumber = count
            }
        }.resume()
    }
}
