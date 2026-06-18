import SwiftUI

struct PersonProfile: Codable {
    let personUid: String
    let firstSeen: String?
    let lastSeen: String?
    let sightingCount: Int
    let threatFlags: Int
    let isStaff: Bool
    let userLabel: String?
    let camerasSeen: [String]
    let sightings: [SightingItem]
}

struct SightingItem: Codable, Identifiable {
    let eventId: Int
    let cameraName: String
    let timestamp: String
    let thumbnailUrl: String?
    let clothingDescription: String?
}

struct PersonProfileView: View {
    let personUid: String
    @State private var profile: PersonProfile?
    @State private var isLoading = true
    @State private var showLabelEditor = false
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if isLoading {
                ProgressView("Loading profile...")
            } else if let error = errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .foregroundColor(.secondary)
                    Button("Retry") {
                        Task { await loadProfile() }
                    }
                    .buttonStyle(.bordered)
                }
            } else if let profile = profile {
                List {
                    // Header Section
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "person.circle.fill")
                                    .font(.system(size: 40))
                                    .foregroundColor(.blue)
                                VStack(alignment: .leading) {
                                    Text(personUid)
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .lineLimit(1)
                                    if let label = profile.userLabel {
                                        Text(label)
                                            .foregroundColor(.blue)
                                            .font(.subheadline)
                                    }
                                }
                            }

                            HStack(spacing: 16) {
                                Label("\(profile.sightingCount) sightings", systemImage: "eye")
                                    .font(.caption)
                                Label("\(profile.threatFlags) flags", systemImage: "flag.fill")
                                    .font(.caption)
                                    .foregroundColor(profile.threatFlags > 0 ? .orange : .secondary)
                            }

                            if profile.isStaff {
                                Label("Staff", systemImage: "checkmark.shield.fill")
                                    .font(.caption)
                                    .foregroundColor(.green)
                            }

                            if let firstSeen = profile.firstSeen {
                                Text("First seen: \(firstSeen)")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                            if let lastSeen = profile.lastSeen {
                                Text("Last seen: \(lastSeen)")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }

                        Button("Edit Label") {
                            showLabelEditor = true
                        }
                        .buttonStyle(.bordered)
                    }

                    // Cameras Seen
                    if !profile.camerasSeen.isEmpty {
                        Section("Cameras Seen") {
                            ForEach(profile.camerasSeen, id: \.self) { camera in
                                Text(camera)
                                    .font(.subheadline)
                            }
                        }
                    }

                    // Sightings Timeline
                    Section("Sightings") {
                        if profile.sightings.isEmpty {
                            Text("No sightings recorded")
                                .foregroundColor(.secondary)
                                .font(.subheadline)
                        }
                        ForEach(profile.sightings) { sighting in
                            NavigationLink(destination: EventDetailView(eventId: sighting.eventId)) {
                                HStack(spacing: 12) {
                                    AsyncImage(url: URL(string: sighting.thumbnailUrl ?? "")) { phase in
                                        if let image = phase.image {
                                            image
                                                .resizable()
                                                .aspectRatio(contentMode: .fill)
                                        } else {
                                            Color.gray
                                                .overlay(Image(systemName: "photo").foregroundColor(.white))
                                        }
                                    }
                                    .frame(width: 60, height: 45)
                                    .cornerRadius(6)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(sighting.cameraName)
                                            .font(.subheadline)
                                            .fontWeight(.medium)
                                        Text(sighting.timestamp)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                        if let clothing = sighting.clothingDescription {
                                            Text(clothing)
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                                .lineLimit(1)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
        }
        .navigationTitle("Person Profile")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadProfile() }
        .sheet(isPresented: $showLabelEditor) {
            LabelEditorView(personUid: personUid)
        }
    }

    func loadProfile() async {
        isLoading = true
        errorMessage = nil
        do {
            profile = try await VisionOSApiService.shared.getPersonProfile(personUid: personUid)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct LabelEditorView: View {
    let personUid: String
    @State private var label: String = ""
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            Form {
                Section("Edit Label") {
                    TextField("Enter label", text: $label)
                }

                Section {
                    Button("Save") {
                        // Save label via API
                        dismiss()
                    }
                    .disabled(label.isEmpty)
                }
            }
            .navigationTitle("Edit Label")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

#Preview {
    NavigationView {
        PersonProfileView(personUid: "person_12345")
    }
}
