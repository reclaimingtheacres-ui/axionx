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

    @MainActor
    private func resolveAuthState() async {

        if BiometricAuthService.hasSavedToken && BiometricAuthService.isOptedIn {
            do {
                try await BiometricAuthService.authenticate(
                    reason: "Sign in to AxionX"
                )
                let injected = await BiometricAuthService.loadAndInjectSession()
                if injected {
                    withAnimation(.easeInOut(duration: 0.35)) { authState = .authenticated }
                    return
                }
                BiometricAuthService.clearSession()
            } catch BiometricError.cancelled {
                // User tapped Cancel — show LoginView with biometric button
            } catch {
                // Scan failed — show LoginView with biometric button
            }

            withAnimation(.easeInOut(duration: 0.25)) { authState = .unauthenticated }
            return
        }

        let hasWebSession = await LoginService.hasValidSession()
        withAnimation(.easeInOut(duration: 0.25)) {
            authState = hasWebSession ? .authenticated : .unauthenticated
        }
    }
}

#Preview {
    ContentView()
}
