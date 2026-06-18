import SwiftUI
import FirebaseAuth

struct LoginView: View {
    @State private var isLoggedIn = false
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Logo
            Image("logo")
                .resizable()
                .frame(width: 120, height: 120)
                .clipShape(RoundedRectangle(cornerRadius: 24))

            // App Name
            Text("Vision OS")
                .font(.largeTitle)
                .fontWeight(.bold)

            Text("Your AI Security")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Spacer()

            // Sign In Button
            Button(action: signInWithGoogle) {
                HStack(spacing: 12) {
                    Image("google_icon")
                        .resizable()
                        .frame(width: 24, height: 24)
                    Text("Sign in with Google")
                        .font(.headline)
                        .foregroundColor(.primary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color(.systemGray4), lineWidth: 1)
                )
            }
            .padding(.horizontal, 40)
            .disabled(isLoading)

            if isLoading {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle())
            }

            Spacer()
        }
        .preferredColorScheme(.dark)
        .alert("Error", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage)
        }
    }

    func signInWithGoogle() {
        isLoading = true
        // Firebase Google Sign-In implementation
        guard let clientID = FirebaseApp.app()?.options.clientID else {
            isLoading = false
            errorMessage = "Firebase configuration error"
            showError = true
            return
        }

        let config = GIDConfiguration(clientID: clientID)
        GIDSignIn.sharedInstance.configuration = config

        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let rootViewController = windowScene.windows.first?.rootViewController else {
            isLoading = false
            return
        }

        GIDSignIn.sharedInstance.signIn(withPresenting: rootViewController) { result, error in
            isLoading = false
            if let error = error {
                errorMessage = error.localizedDescription
                showError = true
                return
            }

            guard let user = result?.user,
                  let idToken = user.idToken?.tokenString else {
                errorMessage = "Failed to get authentication token"
                showError = true
                return
            }

            let credential = GoogleAuthProvider.credential(
                withIDToken: idToken,
                accessToken: user.accessToken.tokenString
            )

            Auth.auth().signIn(with: credential) { authResult, error in
                if let error = error {
                    errorMessage = error.localizedDescription
                    showError = true
                    return
                }
                withAnimation {
                    isLoggedIn = true
                }
            }
        }
    }
}

#Preview {
    LoginView()
}
