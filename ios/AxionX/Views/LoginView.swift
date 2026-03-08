import SwiftUI

/// Native login screen.
/// Visually identical to LaunchScreen.storyboard — white background with the
/// AxionX wordmark at the same vertical position — so the launch→login
/// transition feels like a single continuous screen.
/// A login card slides in below the logo after a brief settle delay.
struct LoginView: View {

    /// Called once the session cookie has been injected into WKWebsiteDataStore.
    var onLoginSuccess: () -> Void

    // MARK: - State

    @State private var email:         String = ""
    @State private var password:      String = ""
    @State private var isLoading:     Bool   = false
    @State private var errorMessage:  String?
    @State private var cardVisible:   Bool   = false

    @FocusState private var focusedField: FormField?
    private enum FormField { case email, password }

    // MARK: - Brand colours (matching LaunchScreen.storyboard exactly)

    private let axionBlue = Color(red: 0.149, green: 0.388, blue: 0.922)
    private let axionGray = Color(red: 0.424, green: 0.443, blue: 0.502)

    // AxionX text intrinsic height at 42pt bold ≈ 52 pt.
    // topPad = screenH/2 - 20 - 26  →  AxionX centre = screenH/2 - 20
    // which matches the LaunchScreen constraint exactly.
    private let axionXHalfHeight: CGFloat = 26

    // MARK: - Body

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .top) {
                Color.white.ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        // Top spacer — pins AxionX centre to LaunchScreen position
                        let topPad = max(geo.size.height / 2 - 20 - axionXHalfHeight, 80)
                        Color.clear.frame(height: topPad)

                        // ── Branding ──────────────────────────────────────────
                        VStack(spacing: 4) {
                            Text("AxionX")
                                .font(.system(size: 42, weight: .bold, design: .default))
                                .foregroundColor(axionBlue)
                                .tracking(-0.5)

                            Text("Field Operations")
                                .font(.system(size: 16, weight: .regular))
                                .foregroundColor(axionGray)
                        }
                        .frame(maxWidth: .infinity)

                        // ── Login card ────────────────────────────────────────
                        if cardVisible {
                            loginCard
                                .padding(.top, 48)
                                .padding(.horizontal, 28)
                                .padding(.bottom, 60)
                                .transition(
                                    .opacity.combined(with: .offset(y: 24))
                                )
                        }
                    }
                }
            }
        }
        .ignoresSafeArea()
        .preferredColorScheme(.light)
        .onAppear {
            withAnimation(
                .spring(response: 0.55, dampingFraction: 0.85).delay(0.18)
            ) {
                cardVisible = true
            }
        }
    }

    // MARK: - Login card

    private var loginCard: some View {
        VStack(spacing: 16) {

            // Email
            VStack(alignment: .leading, spacing: 6) {
                Text("Email")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(axionGray)

                TextField("you@example.com", text: $email)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .autocorrectionDisabled()
                    .textContentType(.emailAddress)
                    .focused($focusedField, equals: .email)
                    .font(.system(size: 15))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 12)
                    .background(Color(white: 0.97))
                    .cornerRadius(10)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color(white: 0.88), lineWidth: 1)
                    )
            }

            // Password
            VStack(alignment: .leading, spacing: 6) {
                Text("Password")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(axionGray)

                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .focused($focusedField, equals: .password)
                    .font(.system(size: 15))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 12)
                    .background(Color(white: 0.97))
                    .cornerRadius(10)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color(white: 0.88), lineWidth: 1)
                    )
                    .onSubmit { Task { await performLogin() } }
            }

            // Inline error
            if let msg = errorMessage {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.system(size: 13))
                    Text(msg)
                        .font(.system(size: 13))
                }
                .foregroundColor(.red)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 2)
                .transition(.opacity)
                .animation(.easeInOut(duration: 0.2), value: errorMessage)
            }

            // Sign In button
            Button(action: { Task { await performLogin() } }) {
                ZStack {
                    if isLoading {
                        ProgressView().tint(.white)
                    } else {
                        Text("Sign In")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(axionBlue)
                .cornerRadius(12)
            }
            .disabled(isLoading || email.isEmpty || password.isEmpty)
            .opacity(isLoading || email.isEmpty || password.isEmpty ? 0.7 : 1.0)
            .padding(.top, 4)
            .animation(.easeInOut(duration: 0.15), value: isLoading)
        }
        .padding(24)
        .background(Color.white)
        .cornerRadius(20)
        .shadow(color: .black.opacity(0.08), radius: 20, x: 0, y: 4)
    }

    // MARK: - Auth

    @MainActor
    private func performLogin() async {
        guard !email.isEmpty, !password.isEmpty else { return }

        focusedField  = nil
        isLoading     = true
        errorMessage  = nil

        do {
            let cookies = try await LoginService.login(email: email, password: password)
            await LoginService.injectCookies(cookies)
            withAnimation(.easeInOut(duration: 0.35)) {
                onLoginSuccess()
            }
        } catch LoginError.invalidCredentials {
            withAnimation { errorMessage = "Incorrect email or password." }
            isLoading = false
        } catch LoginError.networkError {
            withAnimation { errorMessage = "Connection failed. Check your network." }
            isLoading = false
        } catch {
            withAnimation { errorMessage = "Login failed. Please try again." }
            isLoading = false
        }
    }
}

// MARK: - Preview

#Preview {
    LoginView(onLoginSuccess: {})
}
