import SwiftUI

/// Native login screen.
/// Full-screen AppBackground image fills the display — identical to the
/// LaunchScreen — with a frosted-glass login panel layered over the lower half.
/// The panel fades in after a short delay so the branding remains the first
/// thing the user sees.
struct LoginView: View {

    var onLoginSuccess: () -> Void

    // MARK: - State

    @State private var email:        String = ""
    @State private var password:     String = ""
    @State private var isLoading:    Bool   = false
    @State private var errorMessage: String?
    @State private var panelVisible: Bool   = false

    @FocusState private var focusedField: FormField?
    private enum FormField { case email, password }

    // MARK: - Colours

    private let axionBlue = Color(red: 0.149, green: 0.388, blue: 0.922)

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .bottom) {

            // ── Background image — full screen, identical to LaunchScreen ──
            Image("AppBackground")
                .resizable()
                .aspectRatio(contentMode: .fill)
                .ignoresSafeArea()

            // ── Frosted glass login panel — lower portion ─────────────────
            if panelVisible {
                loginPanel
                    .padding(.horizontal, 20)
                    .padding(.bottom, 52)
                    .transition(.opacity.combined(with: .offset(y: 16)))
            }
        }
        .ignoresSafeArea()
        .preferredColorScheme(.dark)
        .onAppear {
            withAnimation(
                .easeOut(duration: 0.45).delay(0.25)
            ) {
                panelVisible = true
            }
        }
    }

    // MARK: - Login panel (frosted glass)

    private var loginPanel: some View {
        VStack(spacing: 18) {

            // Panel heading
            VStack(spacing: 3) {
                Text("Sign In")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(.white)
                Text("AxionX Field Operations")
                    .font(.system(size: 13, weight: .regular))
                    .foregroundColor(.white.opacity(0.6))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.bottom, 4)

            // Email
            VStack(alignment: .leading, spacing: 6) {
                Text("Email")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)
                    .kerning(0.5)

                TextField("", text: $email, prompt: Text("you@company.com").foregroundColor(.white.opacity(0.35)))
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .autocorrectionDisabled()
                    .textContentType(.emailAddress)
                    .focused($focusedField, equals: .email)
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                    .tint(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 13)
                    .background(Color.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))
                    .overlay(
                        RoundedRectangle(cornerRadius: 11)
                            .stroke(Color.white.opacity(0.18), lineWidth: 1)
                    )
            }

            // Password
            VStack(alignment: .leading, spacing: 6) {
                Text("Password")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)
                    .kerning(0.5)

                SecureField("", text: $password, prompt: Text("Password").foregroundColor(.white.opacity(0.35)))
                    .textContentType(.password)
                    .focused($focusedField, equals: .password)
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                    .tint(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 13)
                    .background(Color.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))
                    .overlay(
                        RoundedRectangle(cornerRadius: 11)
                            .stroke(Color.white.opacity(0.18), lineWidth: 1)
                    )
                    .onSubmit { Task { await performLogin() } }
            }

            // Error message
            if let msg = errorMessage {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.system(size: 13))
                    Text(msg)
                        .font(.system(size: 13))
                }
                .foregroundColor(Color(red: 1.0, green: 0.5, blue: 0.5))
                .frame(maxWidth: .infinity, alignment: .leading)
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
                .frame(height: 52)
                .background(
                    axionBlue.opacity(isLoading || email.isEmpty || password.isEmpty ? 0.6 : 1.0)
                )
                .cornerRadius(13)
            }
            .disabled(isLoading || email.isEmpty || password.isEmpty)
            .padding(.top, 4)
            .animation(.easeInOut(duration: 0.15), value: isLoading)
        }
        .padding(24)
        .background {
            // Dark-tinted frosted glass
            RoundedRectangle(cornerRadius: 24)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .fill(Color.black.opacity(0.28))
                )
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24)
                .stroke(Color.white.opacity(0.14), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.4), radius: 32, x: 0, y: 12)
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
