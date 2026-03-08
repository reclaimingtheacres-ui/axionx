import SwiftUI

/// Native login screen.
/// Full-screen AppBackground image — identical to the LaunchScreen — with a
/// frosted-glass login panel over the lower half.
///
/// When a saved Keychain session exists, a Face ID / Touch ID button is shown
/// at the top of the panel so the user can unlock without re-entering credentials.
/// Manual email/password login always remains available as fallback.
struct LoginView: View {

    var onLoginSuccess: () -> Void

    // MARK: - State

    @State private var email:          String = ""
    @State private var password:       String = ""
    @State private var isLoading:      Bool   = false
    @State private var isBiometricBusy: Bool  = false
    @State private var errorMessage:   String?
    @State private var panelVisible:   Bool   = false

    @FocusState private var focusedField: FormField?
    private enum FormField { case email, password }

    // MARK: - Biometric helpers

    private var biometricType: BiometricType { BiometricAuthService.biometricType }
    private var showBiometric: Bool {
        BiometricAuthService.hasSavedSession && biometricType != .none
    }

    // MARK: - Colours

    private let axionBlue = Color(red: 0.149, green: 0.388, blue: 0.922)

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .bottom) {

            // ── Background image — identical to LaunchScreen ───────────────
            Image("AppBackground")
                .resizable()
                .aspectRatio(contentMode: .fill)
                .ignoresSafeArea()

            // ── Frosted glass login panel — lower portion ──────────────────
            if panelVisible {
                loginPanel
                    .padding(.horizontal, 20)
                    .padding(.bottom, 52)
                    .transition(.opacity.combined(with: .offset(y: 16)))
            }

            // ── Non-production environment banner ─────────────────────────
            // Visible in Staging and Local builds so testers are always aware
            // they are NOT connected to the live production server.
            if !AppConfig.isProduction {
                VStack {
                    environmentBanner
                    Spacer()
                }
                .ignoresSafeArea(edges: .top)
            }
        }
        .ignoresSafeArea()
        .preferredColorScheme(.dark)
        .onAppear {
            withAnimation(.easeOut(duration: 0.45).delay(0.25)) {
                panelVisible = true
            }
        }
    }

    // MARK: - Environment banner

    private var environmentBanner: some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 11, weight: .bold))
            Text("\(AppConfig.environmentName.uppercased()) BUILD")
                .font(.system(size: 11, weight: .bold))
                .kerning(0.6)
            Text("·")
                .font(.system(size: 11, weight: .light))
                .opacity(0.7)
            Text(AppConfig.currentBaseURL)
                .font(.system(size: 10, weight: .regular))
                .lineLimit(1)
                .truncationMode(.middle)
                .opacity(0.85)
        }
        .foregroundColor(.black.opacity(0.85))
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .padding(.top, 4)
        .frame(maxWidth: .infinity)
        .background(Color(red: 1.0, green: 0.78, blue: 0.17))
    }

    // MARK: - Login panel

    private var loginPanel: some View {
        VStack(spacing: 18) {

            // ── Biometric button (shown only when a saved session exists) ──
            if showBiometric {
                biometricButton
                    .padding(.bottom, 4)

                divider
            }

            // ── Panel heading ─────────────────────────────────────────────
            VStack(spacing: 3) {
                Text("Sign In")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(.white)
                Text("Enter your credentials")
                    .font(.system(size: 12, weight: .regular))
                    .foregroundColor(.white.opacity(0.55))
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // ── Email ─────────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 6) {
                Text("Email")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)
                    .kerning(0.5)

                TextField("", text: $email,
                          prompt: Text("you@company.com").foregroundColor(.white.opacity(0.35)))
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
                    .overlay(RoundedRectangle(cornerRadius: 11).stroke(Color.white.opacity(0.18), lineWidth: 1))
            }

            // ── Password ──────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 6) {
                Text("Password")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)
                    .kerning(0.5)

                SecureField("", text: $password,
                            prompt: Text("Password").foregroundColor(.white.opacity(0.35)))
                    .textContentType(.password)
                    .focused($focusedField, equals: .password)
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                    .tint(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 13)
                    .background(Color.white.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))
                    .overlay(RoundedRectangle(cornerRadius: 11).stroke(Color.white.opacity(0.18), lineWidth: 1))
                    .onSubmit { Task { await performLogin() } }
            }

            // ── Inline error ──────────────────────────────────────────────
            if let msg = errorMessage {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.circle.fill").font(.system(size: 13))
                    Text(msg).font(.system(size: 13))
                }
                .foregroundColor(Color(red: 1.0, green: 0.5, blue: 0.5))
                .frame(maxWidth: .infinity, alignment: .leading)
                .transition(.opacity)
                .animation(.easeInOut(duration: 0.2), value: errorMessage)
            }

            // ── Sign In button ────────────────────────────────────────────
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
                .background(axionBlue.opacity(isLoading || email.isEmpty || password.isEmpty ? 0.6 : 1.0))
                .cornerRadius(13)
            }
            .disabled(isLoading || email.isEmpty || password.isEmpty)
            .padding(.top, 4)
            .animation(.easeInOut(duration: 0.15), value: isLoading)
        }
        .padding(24)
        .background {
            RoundedRectangle(cornerRadius: 24)
                .fill(.ultraThinMaterial)
                .overlay(RoundedRectangle(cornerRadius: 24).fill(Color.black.opacity(0.28)))
        }
        .overlay { RoundedRectangle(cornerRadius: 24).stroke(Color.white.opacity(0.14), lineWidth: 1) }
        .shadow(color: .black.opacity(0.4), radius: 32, x: 0, y: 12)
    }

    // MARK: - Biometric button

    private var biometricButton: some View {
        Button(action: { Task { await tryBiometric() } }) {
            HStack(spacing: 10) {
                if isBiometricBusy {
                    ProgressView().tint(.white).scaleEffect(0.85)
                } else {
                    Image(systemName: biometricType.systemImageName)
                        .font(.system(size: 20, weight: .medium))
                        .foregroundColor(.white)
                }
                Text(biometricType.label)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.white)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 52)
            .background(Color.white.opacity(0.15), in: RoundedRectangle(cornerRadius: 13))
            .overlay(RoundedRectangle(cornerRadius: 13).stroke(Color.white.opacity(0.25), lineWidth: 1))
        }
        .disabled(isBiometricBusy)
        .animation(.easeInOut(duration: 0.15), value: isBiometricBusy)
    }

    private var divider: some View {
        HStack {
            Rectangle().frame(height: 1).foregroundColor(.white.opacity(0.15))
            Text("or sign in manually")
                .font(.system(size: 11, weight: .regular))
                .foregroundColor(.white.opacity(0.4))
                .fixedSize()
            Rectangle().frame(height: 1).foregroundColor(.white.opacity(0.15))
        }
    }

    // MARK: - Auth actions

    @MainActor
    private func tryBiometric() async {
        isBiometricBusy = true
        errorMessage    = nil
        do {
            try await BiometricAuthService.authenticate(reason: "Sign in to AxionX")
            let injected = await BiometricAuthService.loadAndInjectSession()
            if injected {
                withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
            } else {
                // Keychain session was expired — let the user log in manually
                BiometricAuthService.clearSession()
                errorMessage = "Your session has expired. Please sign in again."
            }
        } catch BiometricError.cancelled {
            // User dismissed the prompt — do nothing
        } catch {
            errorMessage = "Biometric authentication failed."
        }
        isBiometricBusy = false
    }

    @MainActor
    private func performLogin() async {
        guard !email.isEmpty, !password.isEmpty else { return }

        focusedField  = nil
        isLoading     = true
        errorMessage  = nil

        do {
            // loginAndPersist: authenticates, injects cookies, saves to Keychain
            try await LoginService.loginAndPersist(email: email, password: password)
            withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
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
