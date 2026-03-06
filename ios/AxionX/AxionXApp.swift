import SwiftUI
import UIKit
import UserNotifications

// MARK: - App Entry Point

@main
struct AxionXApp: App {

    /// Adaptor keeps an AppDelegate in scope for push notifications and
    /// other UIApplicationDelegate callbacks that SwiftUI doesn't cover yet.
    @UIApplicationDelegateAdaptor(AxionAppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.light) // Force light mode for v1; dark mode TBD
        }
    }
}

// MARK: - App Delegate (push notifications + lifecycle hooks)

final class AxionAppDelegate: NSObject, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self

        // Request permission and register with APNs.
        // Token upload happens in didRegisterForRemoteNotificationsWithDeviceToken below.
        Task { @MainActor in
            PushNotificationService.shared.requestPermissionAndRegister()
        }
        return true
    }

    // MARK: - APNs token received

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        Task { @MainActor in
            PushNotificationService.shared.uploadToken(deviceToken)
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Silently swallow — notifications are non-critical for core functionality.
    }

    // MARK: - App foregrounded: refresh badge count

    func applicationDidBecomeActive(_ application: UIApplication) {
        Task { @MainActor in
            PushNotificationService.shared.refreshUnreadBadge()
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension AxionAppDelegate: UNUserNotificationCenterDelegate {

    /// Show banners even when the app is in the foreground.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    /// When the user taps a notification, navigate to the Alerts screen.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        NotificationCenter.default.post(
            name: .axionOpenNotifications,
            object: nil
        )
        completionHandler()
    }
}

// MARK: - Notification name

extension Notification.Name {
    static let axionOpenNotifications = Notification.Name("axionOpenNotifications")
}
