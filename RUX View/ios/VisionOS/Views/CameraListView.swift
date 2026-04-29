import SwiftUI

struct CameraSummary: Codable, Identifiable {
    let id: String
    let name: String
    let locationName: String
    let mode: String
    let status: String  // online/offline/error
    let lastEventTime: String?
    let unreadAlertCount: Int
}

struct CameraListView: View {
    @State private var cameras: [CameraSummary] = []
    @State private var isRefreshing = false
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationView {
            Group {
                if isLoading {
                    ProgressView("Loading cameras...")
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(error)
                            .foregroundColor(.secondary)
                        Button("Retry") {
                            Task { await refreshCameras() }
                        }
                        .buttonStyle(.bordered)
                    }
                } else if cameras.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "video.slash")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No cameras found")
                            .foregroundColor(.secondary)
                        Text("Add a camera to get started")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } else {
                    List(cameras) { camera in
                        NavigationLink(destination: EventFeedView(cameraId: camera.id)) {
                            CameraRow(camera: camera)
                        }
                    }
                    .refreshable { await refreshCameras() }
                }
            }
            .navigationTitle("Cameras")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(destination: SettingsView()) {
                        Image(systemName: "gear")
                    }
                }
            }
        }
        .task { await loadCameras() }
    }

    func loadCameras() async {
        isLoading = true
        errorMessage = nil
        do {
            cameras = try await VisionOSApiService.shared.getCameras()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func refreshCameras() async {
        isRefreshing = true
        errorMessage = nil
        do {
            cameras = try await VisionOSApiService.shared.getCameras()
        } catch {
            errorMessage = error.localizedDescription
        }
        isRefreshing = false
    }
}

struct CameraRow: View {
    let camera: CameraSummary

    var body: some View {
        HStack(spacing: 12) {
            StatusDot(status: camera.status)
            VStack(alignment: .leading, spacing: 4) {
                Text(camera.name)
                    .font(.headline)
                Text(camera.locationName)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(camera.mode.capitalized)
                    .font(.caption2)
                    .foregroundColor(.blue)
            }
            Spacer()
            if camera.unreadAlertCount > 0 {
                Badge(count: camera.unreadAlertCount)
            }
        }
        .padding(.vertical, 4)
    }
}

struct StatusDot: View {
    let status: String

    var body: some View {
        Circle()
            .fill(statusColor)
            .frame(width: 10, height: 10)
    }

    var statusColor: Color {
        switch status {
        case "online": return .green
        case "offline": return .red
        case "error": return .orange
        default: return .gray
        }
    }
}

struct Badge: View {
    let count: Int

    var body: some View {
        Text("\(count)")
            .font(.caption2)
            .fontWeight(.bold)
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.red)
            .clipShape(Capsule())
    }
}

#Preview {
    CameraListView()
}
