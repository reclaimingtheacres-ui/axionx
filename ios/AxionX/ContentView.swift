import SwiftUI

/// Root view. Controls the splash → main transition and
/// surfaces connectivity state from ConnectivityMonitor.
struct ContentView: View {

    @StateObject private var connectivity = ConnectivityMonitor()
    @State private var splashDone = false

    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()

            if !splashDone {
                // Native splash shown while WebView boots
                SplashView()
                    .transition(.opacity)

            } else if !connectivity.isConnected {
                // Network unreachable before the first load attempt
                OfflineView {
                    // Connectivity monitor will flip isConnected automatically
                    // when the network returns; this closure just forces a re-check
                }
                .transition(.opacity)

            } else {
                // Main content — WebViewContainer manages its own offline overlay
                // for errors that happen after the initial connectivity check
                WebViewContainer()
                    .transition(.opacity)
            }
        }
        .preferredColorScheme(.light)
        .onAppear {
            // Dismiss splash after a short delay to let the WebView start loading
            DispatchQueue.main.asyncAfter(deadline: .now() + AppConfig.splashDelay) {
                withAnimation(.easeInOut(duration: 0.3)) {
                    splashDone = true
                }
            }
        }
    }
}

#Preview {
    ContentView()
}
