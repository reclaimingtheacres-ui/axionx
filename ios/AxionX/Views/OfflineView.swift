import SwiftUI

/// Shown when the AxionX backend cannot be reached.
/// Provides a Retry button that reloads the WebView.
struct OfflineView: View {
    let onRetry: () -> Void

    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()

            VStack(spacing: 20) {
                // Offline icon
                Image(systemName: "wifi.slash")
                    .font(.system(size: 52, weight: .light))
                    .foregroundColor(Color(red: 0.149, green: 0.388, blue: 0.922))

                // Title
                Text("Unable to Connect")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(Color(red: 0.07, green: 0.07, blue: 0.07))

                // Message
                Text(AppConfig.offlineMessage)
                    .font(.system(size: 15))
                    .foregroundColor(Color(red: 0.424, green: 0.443, blue: 0.502))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)

                // Retry button
                Button(action: onRetry) {
                    Text("Try Again")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .frame(width: 180, height: 48)
                        .background(Color(red: 0.149, green: 0.388, blue: 0.922))
                        .cornerRadius(12)
                }
                .padding(.top, 4)
            }
        }
        .preferredColorScheme(.light)
    }
}

#Preview {
    OfflineView(onRetry: {})
}
