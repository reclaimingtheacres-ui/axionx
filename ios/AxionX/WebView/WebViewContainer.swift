import SwiftUI

/// The main container that hosts the WKWebView.
/// Wires up the navigation delegate callbacks so connectivity state
/// is reflected back into SwiftUI without any polling.
struct WebViewContainer: View {
    @StateObject private var store = WebViewStore()
    @State private var isOffline = false

    var body: some View {
        ZStack {
            // WebView — always in the tree so session is never destroyed
            AxionWebView(store: store)
                .ignoresSafeArea()
                .opacity(isOffline ? 0 : 1)

            // Offline overlay
            if isOffline {
                OfflineView {
                    isOffline = false
                    store.reload()
                }
                .transition(.opacity)
            }
        }
        .onAppear {
            wireDelegate()
            store.loadInitial()
        }
    }

    private func wireDelegate() {
        store.navigationDelegate.onLoadFailed = {
            withAnimation { isOffline = true }
        }
        store.navigationDelegate.onLoadSuccess = {
            withAnimation { isOffline = false }
        }
    }
}
