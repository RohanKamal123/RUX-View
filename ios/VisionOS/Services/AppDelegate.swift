import UIKit
import UserNotifications
import Firebase
import FirebaseAuth

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // Configure Firebase
        FirebaseApp.configure()

        // Register for remote notifications
        UNUserNotificationCenter.current().delegate = self
        application.registerForRemoteNotifications()

        // Request notification authorization
        let authOptions: UNAuthorizationOptions = [.alert, .badge, .sound]
        UNUserNotificationCenter.current().requestAuthorization(options: authOptions) { granted, error in
            if granted {
                DispatchQueue.main.async {
                    application.registerForRemoteNotifications()
                }
            }
        }

        return true
    }

    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        // Send APNs token to backend
        let tokenString = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task {
            await registerToken(tokenString)
        }

        // Also pass token to Firebase
        Auth.auth().setAPNSToken(deviceToken, type: .prod)
    }

    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("Failed to register for remote notifications: \(error.localizedDescription)")
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // Show notification even when app is in foreground
        let userInfo = notification.request.content.userInfo

        // Handle Firebase notification
        if let eventId = userInfo["event_id"] as? Int {
            completionHandler([.banner, .sound, .badge])
            return
        }

        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        // Parse notification payload
        let userInfo = response.notification.request.content.userInfo

        if let eventId = userInfo["event_id"] as? Int {
            // Navigate to EventDetailView
            NotificationCenter.default.post(
                name: NSNotification.Name("OpenEvent"),
                object: nil,
                userInfo: ["eventId": eventId]
            )
        } else if let cameraId = userInfo["camera_id"] as? String {
            // Navigate to camera events
            NotificationCenter.default.post(
                name: NSNotification.Name("OpenCamera"),
                object: nil,
                userInfo: ["cameraId": cameraId]
            )
        }

        completionHandler()
    }

    private func registerToken(_ token: String) async {
        guard let user = Auth.auth().currentUser else { return }

        do {
            let idToken = try await user.getIDToken()
            // Send token to backend
            var request = URLRequest(url: URL(string: "https://api.visionos.app/api/notifications/register")!)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer \(idToken)", forHTTPHeaderField: "Authorization")

            let body: [String: Any] = [
                "device_token": token,
                "platform": "ios"
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpResponse = response as? HTTPURLResponse {
                print("Token registration status: \(httpResponse.statusCode)")
            }
        } catch {
            print("Failed to register token: \(error.localizedDescription)")
        }
    }
}
