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
        .task { await resolveAuthState() }
        .onReceive(
            NotificationCenter.default.publisher(for: .axionSessionExpired)
        ) { _ in
            BiometricAuthService.clearSession()
            withAnimation(.easeInOut(duration: 0.35)) {
                authState = .unauthenticated
            }
        }
    }

    @MainActor
    private func resolveAuthState() async {
        print("[Startup] resolveAuthState: begin")

        if BiometricAuthService.hasSavedToken && BiometricAuthService.isOptedIn {
            print("[Startup] resolveAuthState: attempting biometric auto-login")
            do {
                try await BiometricAuthService.authenticate(
                    reason: "Sign in to AxionX"
                )
                print("[Startup] resolveAuthState: biometric auth succeeded, injecting session")
                let injected = await BiometricAuthService.loadAndInjectSession()
                if injected {
                    print("[Startup] resolveAuthState: session injected -> authenticated")
                    withAnimation(.easeInOut(duration: 0.35)) { authState = .authenticated }
                    return
                }
                print("[Startup] resolveAuthState: session injection failed, clearing")
                BiometricAuthService.clearSession()
            } catch BiometricError.cancelled {
                print("[Startup] resolveAuthState: biometric cancelled by user")
            } catch {
                print("[Startup] resolveAuthState: biometric failed: \(error)")
            }

            withAnimation(.easeInOut(duration: 0.25)) { authState = .unauthenticated }
            print("[Startup] resolveAuthState: -> unauthenticated (biometric path)")
            return
        }

        print("[Startup] resolveAuthState: checking web session cookies")
        let hasWebSession = await LoginService.hasValidSession()
        print("[Startup] resolveAuthState: hasValidSession=\(hasWebSession)")
        withAnimation(.easeInOut(duration: 0.25)) {
            authState = hasWebSession ? .authenticated : .unauthenticated
        }
        print("[Startup] resolveAuthState: -> \(hasWebSession ? "authenticated" : "unauthenticated")")
    }
}

extension Notification.Name {
    static let axionSessionExpired = Notification.Name("axionSessionExpired")
}

#Preview {
    ContentView()
}
