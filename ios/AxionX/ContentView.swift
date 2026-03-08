import SwiftUI
import WebKit

/// Root view — manages the full authentication lifecycle.
///
/// Launch flow:
///   1. Show AppBackground (< 100 ms — matches LaunchScreen exactly).
///   2. If Keychain holds a valid session: fire biometric prompt immediately.
///      • Success  → inject session cookie → WebViewContainer.
///      • Cancel   → LoginView (biometric button visible so user can retry).
///      • Failure  → LoginView (biometric button visible).
///   3. If no Keychain session: check WKWebsiteDataStore for an existing
///      web-session cookie (handles users who logged in before biometric was
///      introduced) → WebViewContainer if found, otherwise LoginView.
struct ContentView: View {

    // MARK: - State

    private enum AuthState {
        case checking       // initial — show background only
        case unauthenticated
        case authenticated
    }

    @State private var authState: AuthState = .checking

    // MARK: - Body

    var body: some View {
        ZStack {
            switch authState {

            case .checking:
                Image("AppBackground")
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .ignoresSafeArea()
                    .transition(.opacity)

            case .unauthenticated:
                LoginView(onLoginSuccess: {
                    withAnimation(.easeInOut(duration: 0.35)) {
                        authState = .authenticated
                    }
                })
                .transition(.opacity)

            case .authenticated:
                WebViewContainer()
                    .transition(.opacity)
            }
        }
        .preferredColorScheme(.light)
        .task { await resolveAuthState() }
    }

    // MARK: - Auth resolution

    @MainActor
    private func resolveAuthState() async {

        // ── Path A: Keychain session available → try biometric ────────────
        if BiometricAuthService.hasSavedSession {
            do {
                try await BiometricAuthService.authenticate(
                    reason: "Sign in to AxionX"
                )
                // Biometric passed — inject the stored session cookie
                let injected = await BiometricAuthService.loadAndInjectSession()
                if injected {
                    withAnimation(.easeInOut(duration: 0.35)) { authState = .authenticated }
                    return
                }
                // Cookie was stale — fall through to login screen
                BiometricAuthService.clearSession()
            } catch BiometricError.cancelled {
                // User tapped Cancel — show LoginView with biometric button
            } catch {
                // Scan failed — show LoginView with biometric button
            }

            withAnimation(.easeInOut(duration: 0.25)) { authState = .unauthenticated }
            return
        }

        // ── Path B: No Keychain session — check WKWebsiteDataStore ────────
        // Handles users who authenticated before biometric support was added.
        let hasWebSession = await LoginService.hasValidSession()
        withAnimation(.easeInOut(duration: 0.25)) {
            authState = hasWebSession ? .authenticated : .unauthenticated
        }
    }
}

#Preview {
    ContentView()
}
