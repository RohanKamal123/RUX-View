import SwiftUI

struct EventItem: Codable, Identifiable {
    let id: Int
    let cameraName: String
    let threatLevel: String
    let timestamp: String
    let thumbnailUrl: String?
    let description: String?
    let durationSec: Float?
    let personIds: [String]?
}

struct EventFeedView: View {
    let cameraId: String?
    @State private var events: [EventItem] = []
    @State private var selectedThreat: String? = nil
    @State private var page = 0
    @State private var isLoading = false
    @State private var isLoadingMore = false
    @State private var hasMore = true
    private let pageSize = 20

    var body: some View {
        VStack(spacing: 0) {
            // Threat filter chips
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ThreatChip("All", isSelected: selectedThreat == nil)
                        .onTapGesture { selectedThreat = nil }
                    ThreatChip("HIGH", color: .orange)
                        .onTapGesture { selectedThreat = "HIGH" }
                    ThreatChip("MEDIUM", color: .yellow)
                        .onTapGesture { selectedThreat = "MEDIUM" }
                    ThreatChip("LOW", color: .green)
                        .onTapGesture { selectedThreat = "LOW" }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .background(Color(.systemBackground))

            // Event list
            List {
                ForEach(filteredEvents) { event in
                    NavigationLink(destination: EventDetailView(eventId: event.id)) {
                        EventRow(event: event)
                    }
                }

                if hasMore && !filteredEvents.isEmpty {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .onAppear { loadMore() }
                }
            }
            .listStyle(.plain)
            .refreshable { await refreshEvents() }
        }
        .navigationTitle(cameraId != nil ? "Camera Events" : "All Events")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadEvents() }
    }

    var filteredEvents: [EventItem] {
        guard let threat = selectedThreat else { return events }
        return events.filter { $0.threatLevel == threat }
    }

    func loadEvents() async {
        isLoading = true
        page = 0
        hasMore = true
        do {
            events = try await VisionOSApiService.shared.getEvents(
                cameraId: cameraId,
                threatLevel: selectedThreat,
                limit: pageSize,
                offset: 0
            )
        } catch {
            // Handle error silently
        }
        isLoading = false
    }

    func refreshEvents() async {
        page = 0
        hasMore = true
        do {
            let fresh = try await VisionOSApiService.shared.getEvents(
                cameraId: cameraId,
                threatLevel: selectedThreat,
                limit: pageSize,
                offset: 0
            )
            events = fresh
        } catch {
            // Handle error silently
        }
    }

    func loadMore() {
        guard !isLoadingMore, hasMore else { return }
        isLoadingMore = true
        page += 1
        Task {
            do {
                let more = try await VisionOSApiService.shared.getEvents(
                    cameraId: cameraId,
                    threatLevel: selectedThreat,
                    limit: pageSize,
                    offset: page * pageSize
                )
                if more.isEmpty {
                    hasMore = false
                } else {
                    events.append(contentsOf: more)
                }
            } catch {
                hasMore = false
            }
            isLoadingMore = false
        }
    }
}

struct ThreatChip: View {
    let title: String
    var color: Color = .gray
    var isSelected: Bool = false

    init(_ title: String, color: Color = .gray, isSelected: Bool = false) {
        self.title = title
        self.color = color
        self.isSelected = isSelected
    }

    var body: some View {
        Text(title)
            .font(.caption)
            .fontWeight(isSelected ? .bold : .regular)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(isSelected ? color.opacity(0.2) : Color(.systemGray6))
            .foregroundColor(isSelected ? color : .primary)
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .stroke(isSelected ? color : Color.clear, lineWidth: 1)
            )
    }
}

struct ThreatBadge: View {
    let level: String

    var body: some View {
        Text(level)
            .font(.caption2)
            .fontWeight(.bold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(badgeColor.opacity(0.2))
            .foregroundColor(badgeColor)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    var badgeColor: Color {
        switch level {
        case "EMERGENCY": return .red
        case "HIGH": return .orange
        case "MEDIUM": return .yellow
        case "LOW": return .green
        default: return .gray
        }
    }
}

struct EventRow: View {
    let event: EventItem

    var body: some View {
        HStack(spacing: 12) {
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
            .frame(width: 80, height: 60)
            .cornerRadius(8)

            // Details
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    ThreatBadge(level: event.threatLevel)
                    Text(event.cameraName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Text(event.description ?? "Motion detected")
                    .font(.subheadline)
                    .lineLimit(2)
                Text(event.timestamp)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    NavigationView {
        EventFeedView(cameraId: nil)
    }
}
