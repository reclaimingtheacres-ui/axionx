import SwiftUI
import UIKit
import UserNotifications
import BackgroundTasks

// MARK: - App Entry Point

@main
struct AxionXApp: App {

    @UIApplicationDelegateAdaptor(AxionAppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.light)
                .environmentObject(SyncManager.shared)
                .environmentObject(FieldStatusManager.shared)
        }
    }
}

// MARK: - App Delegate

final class AxionAppDelegate: NSObject, UIApplicationDelegate {

    private static let bgSyncID = "com.axionx.sync"

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self

        // Push notifications
        Task { @MainActor in
            PushNotificationService.shared.requestPermissionAndRegister()
        }

        // Restore field status and start location service
        _ = FieldStatusManager.shared

        // Register background app-refresh task for queued item sync
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.bgSyncID,
            using: nil
        ) { [weak self] task in
            self?.handleBGSync(task: task as! BGAppRefreshTask)
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
    ) {}

    // MARK: - App foregrounded

    func applicationDidBecomeActive(_ application: UIApplication) {
        Task { @MainActor in
            PushNotificationService.shared.refreshUnreadBadge()
            await SyncManager.shared.syncNow()
        }
    }

    // MARK: - Background app refresh

    private func handleBGSync(task: BGAppRefreshTask) {
        scheduleNextBGSync()
        let work = Task {
            await SyncManager.shared.syncNow()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = {
            work.cancel()
            task.setTaskCompleted(success: false)
        }
    }

    static func scheduleNextBGSync() {
        let req = BGAppRefreshTaskRequest(identifier: bgSyncID)
        req.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(req)
    }

    private func scheduleNextBGSync() { Self.scheduleNextBGSync() }
}

// MARK: - UNUserNotificationCenterDelegate

extension AxionAppDelegate: UNUserNotificationCenterDelegate {

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let payload = response.notification.request.content.userInfo
        var info: [String: Any] = [:]
        if let t = payload["type"] as? String { info["type"] = t }
        if let c = payload["conv_id"] as? Int { info["conv_id"] = c }
        else if let cs = payload["conv_id"] as? String, let ci = Int(cs) { info["conv_id"] = ci }
        NotificationCenter.default.post(name: .axionOpenNotifications, object: nil, userInfo: info)
        completionHandler()
    }
}

// MARK: - Notification name

extension Notification.Name {
    static let axionOpenNotifications = Notification.Name("axionOpenNotifications")
}
