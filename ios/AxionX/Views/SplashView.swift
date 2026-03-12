import SwiftUI

struct SplashView: View {

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Color(red: 0.06, green: 0.08, blue: 0.14)
                    .ignoresSafeArea()

                Image("AppBackground")
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: geo.size.width, height: geo.size.height)
                    .clipped()
                    .ignoresSafeArea()
            }
        }
        .ignoresSafeArea()
        .preferredColorScheme(.dark)
    }
}

#Preview {
    SplashView()
}
