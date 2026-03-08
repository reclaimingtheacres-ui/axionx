import SwiftUI
import WebKit

/// Root view.
/// On every launch the session cookie is checked (< 100 ms) while the same
/// full-screen AppBackground image is shown — matching the LaunchScreen exactly.
/// Returning users skip straight to the WebView; new users see the LoginView
/// with the frosted-glass panel fading in over the background.
struct ContentView: View {

    // MARK: - State

    private enum AuthState { case checking, unauthenticated, authenticated }

    @State private var authState: AuthState = .checking

    // MARK: - Body

    var body: some View {
        ZStack {
            switch authState {

            case .checking:
                // Shown for < 100 ms while session cookie is read.
                // Full-screen background image — visually identical to LaunchScreen.
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
        .task {
            let hasSession = await LoginService.hasValidSession()
            await MainActor.run {
                withAnimation(.easeInOut(duration: 0.25)) {
                    authState = hasSession ? .authenticated : .unauthenticated
                }
            }
        }
    }
}

#Preview {
    ContentView()
}
