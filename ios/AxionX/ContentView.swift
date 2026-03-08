import SwiftUI
import WebKit

/// Root view.
/// On first launch: checks for an existing session cookie (nearly instant) while
/// showing the same AxionX branding as the LaunchScreen, then either skips
/// straight to the WebView (returning user) or presents the native LoginView.
struct ContentView: View {

    // MARK: - State

    private enum AuthState { case checking, unauthenticated, authenticated }

    @State private var authState: AuthState = .checking

    // MARK: - Body

    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()

            switch authState {

            case .checking:
                // Shown while the session cookie check runs (< 100 ms).
                // Identical to LaunchScreen so the user sees no visual break.
                brandingView
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
        .task {
            let hasSession = await LoginService.hasValidSession()
            await MainActor.run {
                withAnimation(.easeInOut(duration: 0.25)) {
                    authState = hasSession ? .authenticated : .unauthenticated
                }
            }
        }
    }

    // MARK: - Branding (matches LaunchScreen.storyboard exactly)

    private var brandingView: some View {
        ZStack {
            Color.white.ignoresSafeArea()
            VStack(spacing: 4) {
                Text("AxionX")
                    .font(.system(size: 42, weight: .bold, design: .default))
                    .foregroundColor(Color(red: 0.149, green: 0.388, blue: 0.922))
                    .tracking(-0.5)
                Text("Field Operations")
                    .font(.system(size: 16, weight: .regular))
                    .foregroundColor(Color(red: 0.424, green: 0.443, blue: 0.502))
            }
            .offset(y: -20)
        }
    }
}

#Preview {
    ContentView()
}
