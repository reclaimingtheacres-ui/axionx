import SwiftUI

struct LoginView: View {

    var onLoginSuccess: () -> Void

    @State private var email:           String = ""
    @State private var password:        String = ""
    @State private var isLoading:       Bool   = false
    @State private var isBiometricBusy: Bool   = false
    @State private var errorMessage:    String?
    @State private var panelVisible:    Bool   = false
    @State private var showBiometricPrompt: Bool = false
    @State private var pendingAuthToken: String?

    @FocusState private var focusedField: FormField?
    private enum FormField { case email, password }

    private var biometricType: BiometricType { BiometricAuthService.biometricType }
    private var showBiometric: Bool {
        BiometricAuthService.hasSavedToken && biometricType != .none
    }

    private let axionBlue = Color(red: 0.149, green: 0.388, blue: 0.922)

    var body: some View {
        ZStack(alignment: .bottom) {

            Image("AppBackground")
                .resizable()
                .aspectRatio(contentMode: .fill)
                .ignoresSafeArea()

            if panelVisible {
                loginPanel
                    .padding(.horizontal, 20)
                    .padding(.bottom, 52)
                    .transition(.opacity.combined(with: .offset(y: 16)))
            }

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
        .alert(biometricPromptTitle, isPresented: $showBiometricPrompt) {
            Button("Enable") {
                if let token = pendingAuthToken {
                    BiometricAuthService.saveToken(token)
                }
                pendingAuthToken = nil
                withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
            }
            Button("Not Now", role: .cancel) {
                BiometricAuthService.setDeclined(true)
                if let token = pendingAuthToken {
                    Task { await LoginService.revokeToken(token) }
                }
                pendingAuthToken = nil
                withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
            }
        } message: {
            Text(biometricPromptMessage)
        }
    }

    private var biometricPromptTitle: String {
        "Enable \(biometricType.settingsLabel)?"
    }

    private var biometricPromptMessage: String {
        "Use \(biometricType.settingsLabel) for faster, secure sign in next time you open AxionX."
    }

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

    private var loginPanel: some View {
        VStack(spacing: 18) {

            if showBiometric {
                biometricButton
                    .padding(.bottom, 4)

                divider
            }

            VStack(spacing: 3) {
                Text("Sign In")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(.white)
                Text("Enter your credentials")
                    .font(.system(size: 12, weight: .regular))
                    .foregroundColor(.white.opacity(0.55))
            }
            .frame(maxWidth: .infinity, alignment: .leading)

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
                BiometricAuthService.clearSession()
                errorMessage = "Your session has expired. Please sign in again."
            }
        } catch BiometricError.cancelled {
            // User dismissed — do nothing
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

        let needsToken = BiometricAuthService.shouldPromptOptIn || BiometricAuthService.isOptedIn

        do {
            let result = try await LoginService.loginAndPersist(
                email: email, password: password, requestToken: needsToken
            )

            if let token = result.authToken, BiometricAuthService.shouldPromptOptIn {
                pendingAuthToken = token
                isLoading = false
                showBiometricPrompt = true
            } else if let token = result.authToken, BiometricAuthService.isOptedIn {
                BiometricAuthService.saveToken(token)
                withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
            } else {
                withAnimation(.easeInOut(duration: 0.35)) { onLoginSuccess() }
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

#Preview {
    LoginView(onLoginSuccess: {})
}
