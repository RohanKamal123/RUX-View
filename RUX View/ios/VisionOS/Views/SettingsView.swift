import SwiftUI

struct AppSettings: Codable {
    var notificationsEnabled: Bool
    var highAlertVibration: Bool
    var emergencyAlertSound: Bool
    var digestTime: String
    var theme: String  // "system" / "light" / "dark"
}

struct SettingsView: View {
    @State private var settings = AppSettings(
        notificationsEnabled: true,
        highAlertVibration: true,
        emergencyAlertSound: true,
        digestTime: "22:00",
        theme: "system"
    )
    @State private var showingLogoutAlert = false
    @State private var showingDeleteAlert = false

    var body: some View {
        NavigationView {
            Form {
                Section("Notifications") {
                    Toggle("Push Notifications", isOn: $settings.notificationsEnabled)
                        .onChange(of: settings.notificationsEnabled) { _ in
                            saveSettings()
                        }
                    Toggle("Vibrate on HIGH", isOn: $settings.highAlertVibration)
                        .onChange(of: settings.highAlertVibration) { _ in
                            saveSettings()
                        }
                    Toggle("Emergency Sound", isOn: $settings.emergencyAlertSound)
                        .onChange(of: settings.emergencyAlertSound) { _ in
                            saveSettings()
                        }
                }

                Section("Digest") {
                    DatePicker("Daily Digest Time",
                        selection: Binding(
                            get: { parseTime(settings.digestTime) },
                            set: { settings.digestTime = formatTime($0) }
                        ),
                        displayedComponents: .hourAndMinute
                    )
                    .onChange(of: settings.digestTime) { _ in
                        saveSettings()
                    }
                }

                Section("Appearance") {
                    Picker("Theme", selection: $settings.theme) {
                        Text("System").tag("system")
                        Text("Light").tag("light")
                        Text("Dark").tag("dark")
                    }
                    .onChange(of: settings.theme) { _ in
                        saveSettings()
                        applyTheme()
                    }
                }

                Section("Account") {
                    Button("Logout", role: .destructive) {
                        showingLogoutAlert = true
                    }
                    Button("Delete Account", role: .destructive) {
                        showingDeleteAlert = true
                    }
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("Tier")
                        Spacer()
                        Text("Household")
                            .foregroundColor(.blue)
                    }
                }
            }
            .navigationTitle("Settings")
        }
        .onAppear {
            loadSettings()
        }
        .alert("Logout", isPresented: $showingLogoutAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Logout", role: .destructive) { logout() }
        } message: {
            Text("Are you sure you want to logout?")
        }
        .alert("Delete Account", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) { deleteAccount() }
        } message: {
            Text("This action is irreversible. All your data will be permanently deleted.")
        }
    }

    func parseTime(_ timeString: String) -> Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.date(from: timeString) ?? Date()
    }

    func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }

    func saveSettings() {
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: "app_settings")
        }
    }

    func loadSettings() {
        if let data = UserDefaults.standard.data(forKey: "app_settings"),
           let saved = try? JSONDecoder().decode(AppSettings.self, from: data) {
            settings = saved
        }
    }

    func applyTheme() {
        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = windowScene.windows.first else { return }

        switch settings.theme {
        case "light":
            window.overrideUserInterfaceStyle = .light
        case "dark":
            window.overrideUserInterfaceStyle = .dark
        default:
            window.overrideUserInterfaceStyle = .unspecified
        }
    }

    func logout() {
        do {
            try FirebaseAuth.Auth.auth().signOut()
            // Navigate to login screen
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let window = windowScene.windows.first {
                window.rootViewController = UIHostingController(rootView: LoginView())
            }
        } catch {
            // Handle error
        }
    }

    func deleteAccount() {
        guard let user = FirebaseAuth.Auth.auth().currentUser else { return }
        user.delete { error in
            if error == nil {
                // Navigate to login screen
                if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                   let window = windowScene.windows.first {
                    window.rootViewController = UIHostingController(rootView: LoginView())
                }
            }
        }
    }
}

#Preview {
    SettingsView()
}
