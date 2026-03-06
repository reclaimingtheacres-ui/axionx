import SwiftUI
import UIKit

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

// MARK: - App Delegate (push notification readiness + lifecycle hooks)

final class AxionAppDelegate: NSObject, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // ── Push notifications (register here when ready for v2) ────────────────
        // let center = UNUserNotificationCenter.current()
        // center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
        //     if granted { application.registerForRemoteNotifications() }
        // }
        return true
    }

    // ── Called after successful APNs registration ─────────────────────────────
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        // Future v2: forward device token to AxionX backend
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        _ = tokenString // suppress unused warning
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Future v2: handle registration failure
    }
}
