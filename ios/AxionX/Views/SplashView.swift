import SwiftUI

/// Native splash screen shown briefly while the WebView initialises.
/// White background with AxionX branding — no black flash.
struct SplashView: View {

    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()

            VStack(spacing: 8) {
                // ── Logo / Wordmark ─────────────────────────────────────────
                // When branding assets are ready, replace this with:
                //   Image("axionx-wordmark")
                //       .resizable()
                //       .scaledToFit()
                //       .frame(maxWidth: 220)
                Text("AxionX")
                    .font(.system(size: 44, weight: .bold, design: .default))
                    .foregroundColor(Color(red: 0.149, green: 0.388, blue: 0.922))
                    .tracking(-0.5)

                Text("Field Operations")
                    .font(.system(size: 16, weight: .regular))
                    .foregroundColor(Color(red: 0.424, green: 0.443, blue: 0.502))
            }
        }
        .preferredColorScheme(.light)
    }
}

#Preview {
    SplashView()
}
