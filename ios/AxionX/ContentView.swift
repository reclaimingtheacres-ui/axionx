import SwiftUI
import WebKit

struct ContentView: View {

    private enum AuthState {
        case checking
        case unauthenticated
        case authenticated
    }

    @State private var authState: AuthState = .checking

    var body: some View {
        ZStack {
            switch authState {

            case .checking:
                Color(red: 0.06, green: 0.08, blue: 0.14)
                    .ignoresSafeArea()
                Image("AppBackground")
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .ignoresSafeArea()
                    .transition(.opacity)

            case .unauthenticated:
                LoginView(onLoginSuccess: {
                    print("[Startup] Login success callback fired")
                    withAnimation(.easeInOut(duration: 0.35)) {
                        authState = .authenticated
                    }
                })
                .transition(.opacity)

            case .authenticated:
                WebViewContainer()
                    .transition(.opacity)
                    .onAppear { print("[Startup] WebViewContainer visible") }
            }
        }
        .ignoresSafeArea()
        .task { resolveAuthState() }
        .onReceive(
            NotificationCenter.default.publisher(for: .axionSessionExpired)
        ) { _ in
            // Suppress session-expired transitions while a document preview is active
            // or the 8-second post-dismiss restore window is running.
            // The webView.load(returnURL) after QL dismissal can hit a server-side
            // redirect to /login if the Flask session expired; without this guard
            // the auth state would flip to .unauthenticated, destroying WebViewContainer
            // and its WKWebView, causing loadInitial() to reload /m/schedule/today.
            if DocumentPreviewHandler.shared.isSuppressingAuthChallenges {
                print("[ContentView] axionSessionExpired suppressed — document preview active or restoring")
                return
            }
            print("[ContentView] Session expired notification received")
            LoginService.markSessionInactive()
            BiometricAuthService.clearSession()
            withAnimation(.easeInOut(duration: 0.35)) {
                authState = .unauthenticated
            }
        }
    }

    @MainActor
    private func resolveAuthState() {
        // DOCUMENT PREVIEW GUARD — critical fix.
        //
        // QLPreviewController is presented .fullScreen from topViewController(),
        // which resolves to the UIHostingController that hosts this ContentView.
        // UIKit calls viewWillDisappear/viewDidDisappear on the hosting controller
        // while QL is visible, then viewWillAppear/viewDidAppear when QL dismisses.
        // SwiftUI's .task modifier respects UIKit's viewDidAppear/viewDidDisappear,
        // so it CANCELS the running task when QL opens and RE-FIRES resolveAuthState()
        // when QL closes — before previewControllerDidDismiss has had a chance to fire.
        //
        // Without this guard: resolveAuthState() sees a saved biometric token and calls
        // doBiometricAuth(), presenting a Face ID challenge. On success, authState cycles
        // to .authenticated, WebViewContainer is recreated with a fresh WKWebView (nil
        // URL), loadInitial() runs, and the user lands on /m/schedule/today.
        //
        // With the guard: isPresentingDocument is still true at the moment .task re-fires
        // (UIHostingController viewDidAppear precedes previewControllerDidDismiss), so
        // isSuppressingAuthChallenges returns true and we bail out immediately.
        if DocumentPreviewHandler.shared.isSuppressingAuthChallenges {
            print("[ContentView] resolveAuthState suppressed — document preview active or restoring")
            return
        }

        print("[Startup] resolveAuthState: begin")

        if BiometricAuthService.hasSavedToken && BiometricAuthService.isOptedIn {
            print("[Startup] resolveAuthState: biometric token saved + opted in, will attempt biometric")
            Task {
                await doBiometricAuth()
            }
            return
        }

        let hasSession = LoginService.hasActiveSessionFlag()
        print("[Startup] resolveAuthState: hasActiveSessionFlag=\(hasSession)")
        withAnimation(.easeInOut(duration: 0.25)) {
            authState = hasSession ? .authenticated : .unauthenticated
        }
        print("[Startup] resolveAuthState: -> \(hasSession ? "authenticated" : "unauthenticated")")
    }

    @MainActor
    private func doBiometricAuth() async {
        print("[Startup] doBiometricAuth: attempting biometric authentication")
        do {
            try await BiometricAuthService.authenticate(
                reason: "Sign in to AxionX"
            )
            print("[Startup] doBiometricAuth: biometric auth succeeded, injecting session")
            let injected = await BiometricAuthService.loadAndInjectSession()
            if injected {
                LoginService.markSessionActive()
                print("[Startup] doBiometricAuth: session injected -> authenticated")
                withAnimation(.easeInOut(duration: 0.35)) { authState = .authenticated }
                return
            }
            print("[Startup] doBiometricAuth: session injection failed, clearing")
            LoginService.markSessionInactive()
            BiometricAuthService.clearSession()
        } catch BiometricError.cancelled {
            print("[Startup] doBiometricAuth: biometric cancelled by user")
        } catch {
            print("[Startup] doBiometricAuth: biometric failed: \(error)")
        }

        withAnimation(.easeInOut(duration: 0.25)) { authState = .unauthenticated }
        print("[Startup] doBiometricAuth: -> unauthenticated")
    }
}

extension Notification.Name {
    static let axionSessionExpired = Notification.Name("axionSessionExpired")
}

#Preview {
    ContentView()
}
