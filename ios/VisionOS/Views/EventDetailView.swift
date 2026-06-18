import SwiftUI

struct EventDetail: Codable {
    let id: Int
    let cameraName: String
    let cameraId: String
    let threatLevel: String
    let timestampStart: String
    let timestampEnd: String?
    let durationSec: Float?
    let thumbnailUrl: String?
    let description: String?
    let gemmaAnalysis: String?
    let geminiDecision: String?
    let personIds: [String]?
    let audioTranscript: String?
    let audioInterpretation: String?
}

struct EventDetailView: View {
    let eventId: Int
    @State private var event: EventDetail?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            if isLoading {
                SkeletonView()
            } else if let error = errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .foregroundColor(.secondary)
                    Button("Retry") {
                        Task { await loadEvent() }
                    }
                    .buttonStyle(.bordered)
                }
                .padding(.top, 100)
            } else if let event = event {
                VStack(alignment: .leading, spacing: 0) {
                    // Thumbnail
                    AsyncImage(url: URL(string: event.thumbnailUrl ?? "")) { phase in
                        if let image = phase.image {
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } else if phase.error != nil {
                            Color.gray
                                .overlay(Image(systemName: "photo").foregroundColor(.white))
                        } else {
                            Color.gray
                                .overlay(ProgressView().tint(.white))
                        }
                    }
                    .frame(height: 250)
                    .clipped()

                    // Details
                    VStack(alignment: .leading, spacing: 16) {
                        // Header
                        HStack {
                            ThreatBadge(level: event.threatLevel)
                            Text(event.cameraName)
                                .font(.headline)
                            Spacer()
                            Text(event.timestampStart)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        // Description
                        if let description = event.description, !description.isEmpty {
                            Text(description)
                                .font(.body)
                        }

                        // Duration
                        if let duration = event.durationSec {
                            Label("Duration: \(Int(duration))s", systemImage: "clock")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }

                        // AI Analysis
                        if let gemmaAnalysis = event.gemmaAnalysis {
                            SectionView("AI Analysis") {
                                Text(gemmaAnalysis)
                                    .font(.subheadline)
                            }
                        }

                        if let geminiDecision = event.geminiDecision {
                            SectionView("AI Decision") {
                                Text(geminiDecision)
                                    .font(.subheadline)
                                    .foregroundColor(.blue)
                            }
                        }

                        // Person list
                        if let persons = event.personIds, !persons.isEmpty {
                            SectionView("Persons") {
                                ForEach(persons, id: \.self) { uid in
                                    NavigationLink(destination: PersonProfileView(personUid: uid)) {
                                        HStack {
                                            Image(systemName: "person.fill")
                                                .foregroundColor(.blue)
                                            Text(uid)
                                                .font(.subheadline)
                                                .foregroundColor(.blue)
                                        }
                                    }
                                }
                            }
                        }

                        // Audio section
                        if let transcript = event.audioTranscript {
                            SectionView("Audio Transcript") {
                                Text(transcript)
                                    .font(.subheadline)
                            }
                        }

                        if let interpretation = event.audioInterpretation {
                            SectionView("Interpretation") {
                                Text(interpretation)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("Event Detail")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadEvent() }
    }

    func loadEvent() async {
        isLoading = true
        errorMessage = nil
        do {
            event = try await VisionOSApiService.shared.getEventDetail(eventId: eventId)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct SectionView<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
                .foregroundColor(.primary)
            content
                .padding(.leading, 4)
        }
        .padding(.vertical, 4)
    }
}

struct SkeletonView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Rectangle()
                .fill(Color.gray.opacity(0.3))
                .frame(height: 250)
            VStack(alignment: .leading, spacing: 12) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(height: 20)
                    .frame(width: 200)
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(height: 16)
                    .frame(width: 150)
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(height: 100)
            }
            .padding()
        }
    }
}

#Preview {
    NavigationView {
        EventDetailView(eventId: 1)
    }
}
