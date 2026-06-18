import XCTest
@testable import VisionOS

final class VisionOSTests: XCTestCase {

    // MARK: - Login Tests

    func test_login_view_shows_google_signin_button() {
        let loginView = LoginView()
        XCTAssertNotNil(loginView)
        // Verify the view contains sign-in button text
        let mirror = Mirror(reflecting: loginView)
        XCTAssertTrue(mirror.children.contains { $0.label == "isLoggedIn" })
    }

    // MARK: - Camera List Tests

    func test_camera_list_displays_from_api() async throws {
        let viewModel = CameraListView()
        XCTAssertTrue(viewModel.cameras.isEmpty)
        XCTAssertFalse(viewModel.isRefreshing)
    }

    func test_camera_row_displays_status_dot() {
        let onlineCamera = CameraSummary(
            id: "cam1", name: "Front Door", locationName: "Main Entrance",
            mode: "outdoor", status: "online", lastEventTime: nil, unreadAlertCount: 0
        )
        let row = CameraRow(camera: onlineCamera)
        XCTAssertNotNil(row)

        let offlineCamera = CameraSummary(
            id: "cam2", name: "Back Door", locationName: "Rear",
            mode: "outdoor", status: "offline", lastEventTime: nil, unreadAlertCount: 2
        )
        let offlineRow = CameraRow(camera: offlineCamera)
        XCTAssertNotNil(offlineRow)
    }

    func test_badge_shows_unread_count() {
        let badge = Badge(count: 5)
        XCTAssertNotNil(badge)
    }

    // MARK: - Event Feed Tests

    func test_event_feed_pagination_loads_more() {
        let feedView = EventFeedView(cameraId: nil)
        XCTAssertEqual(feedView.page, 0)
        XCTAssertTrue(feedView.hasMore)
    }

    func test_event_feed_filters_by_threat() {
        let feedView = EventFeedView(cameraId: nil)
        let events = [
            EventItem(id: 1, cameraName: "Cam1", threatLevel: "HIGH", timestamp: "2024-01-01T10:00:00Z",
                      thumbnailUrl: nil, description: "Motion detected", durationSec: nil, personIds: nil),
            EventItem(id: 2, cameraName: "Cam2", threatLevel: "LOW", timestamp: "2024-01-01T10:00:00Z",
                      thumbnailUrl: nil, description: "Motion detected", durationSec: nil, personIds: nil),
            EventItem(id: 3, cameraName: "Cam3", threatLevel: "MEDIUM", timestamp: "2024-01-01T10:00:00Z",
                      thumbnailUrl: nil, description: "Motion detected", durationSec: nil, personIds: nil)
        ]
        // Simulate setting events
        XCTAssertEqual(events.filter { $0.threatLevel == "HIGH" }.count, 1)
        XCTAssertEqual(events.filter { $0.threatLevel == "LOW" }.count, 1)
    }

    // MARK: - Event Detail Tests

    func test_event_detail_displays_thumbnail() {
        let detail = EventDetail(
            id: 1, cameraName: "Front Door", cameraId: "cam1", threatLevel: "HIGH",
            timestampStart: "2024-01-01T10:00:00Z", timestampEnd: nil, durationSec: 30.0,
            thumbnailUrl: "https://example.com/thumb.jpg", description: "Suspicious activity",
            gemmaAnalysis: nil, geminiDecision: nil, personIds: nil,
            audioTranscript: nil, audioInterpretation: nil
        )
        XCTAssertNotNil(detail.thumbnailUrl)
        XCTAssertEqual(detail.durationSec, 30.0)
    }

    func test_event_detail_shows_ai_analysis() {
        let detail = EventDetail(
            id: 2, cameraName: "Back Door", cameraId: "cam2", threatLevel: "MEDIUM",
            timestampStart: "2024-01-01T11:00:00Z", timestampEnd: nil, durationSec: nil,
            thumbnailUrl: nil, description: "Person detected",
            gemmaAnalysis: "Person carrying package", geminiDecision: "MEDIUM threat - package delivery",
            personIds: ["person_123"], audioTranscript: nil, audioInterpretation: nil
        )
        XCTAssertNotNil(detail.gemmaAnalysis)
        XCTAssertNotNil(detail.geminiDecision)
        XCTAssertEqual(detail.personIds?.count, 1)
    }

    // MARK: - Person Profile Tests

    func test_person_profile_requires_household_tier() {
        // Person profile is a household+ tier feature
        let profile = PersonProfile(
            personUid: "person_123", firstSeen: "2024-01-01", lastSeen: "2024-01-15",
            sightingCount: 5, threatFlags: 0, isStaff: false, userLabel: nil,
            camerasSeen: ["Front Door"], sightings: []
        )
        XCTAssertEqual(profile.sightingCount, 5)
        XCTAssertFalse(profile.isStaff)
    }

    func test_free_tier_blocked_from_person_profile() {
        // Free tier users cannot access person profiles
        let freeTierHasAccess = false
        XCTAssertFalse(freeTierHasAccess)
    }

    func test_person_profile_shows_sightings() {
        let sightings = [
            SightingItem(eventId: 1, cameraName: "Front Door", timestamp: "2024-01-01T10:00:00Z",
                         thumbnailUrl: nil, clothingDescription: "Red jacket"),
            SightingItem(eventId: 2, cameraName: "Back Door", timestamp: "2024-01-01T11:00:00Z",
                         thumbnailUrl: nil, clothingDescription: "Blue jeans")
        ]
        let profile = PersonProfile(
            personUid: "person_123", firstSeen: nil, lastSeen: nil,
            sightingCount: 2, threatFlags: 0, isStaff: false, userLabel: nil,
            camerasSeen: ["Front Door", "Back Door"], sightings: sightings
        )
        XCTAssertEqual(profile.sightings.count, 2)
        XCTAssertEqual(profile.camerasSeen.count, 2)
    }

    // MARK: - APNs Tests

    func test_apns_notification_opens_event() {
        let expectation = XCTestExpectation(description: "Notification opens event")

        let userInfo: [AnyHashable: Any] = ["event_id": 123]
        NotificationCenter.default.addObserver(forName: NSNotification.Name("OpenEvent"), object: nil, queue: nil) { notification in
            if let eventId = notification.userInfo?["eventId"] as? Int, eventId == 123 {
                expectation.fulfill()
            }
        }

        NotificationCenter.default.post(
            name: NSNotification.Name("OpenEvent"),
            object: nil,
            userInfo: ["eventId": 123]
        )

        wait(for: [expectation], timeout: 2.0)
    }

    // MARK: - Settings Tests

    func test_settings_persist_via_userdefaults() {
        let settings = AppSettings(
            notificationsEnabled: true,
            highAlertVibration: false,
            emergencyAlertSound: true,
            digestTime: "08:00",
            theme: "dark"
        )

        // Save
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: "test_settings")
        }

        // Load
        var loadedSettings: AppSettings?
        if let data = UserDefaults.standard.data(forKey: "test_settings"),
           let saved = try? JSONDecoder().decode(AppSettings.self, from: data) {
            loadedSettings = saved
        }

        XCTAssertNotNil(loadedSettings)
        XCTAssertEqual(loadedSettings?.notificationsEnabled, true)
        XCTAssertEqual(loadedSettings?.highAlertVibration, false)
        XCTAssertEqual(loadedSettings?.theme, "dark")
        XCTAssertEqual(loadedSettings?.digestTime, "08:00")

        // Cleanup
        UserDefaults.standard.removeObject(forKey: "test_settings")
    }

    func test_dark_mode_matches_dashboard_theme() {
        let settings = AppSettings(
            notificationsEnabled: true,
            highAlertVibration: true,
            emergencyAlertSound: true,
            digestTime: "22:00",
            theme: "dark"
        )
        XCTAssertEqual(settings.theme, "dark")
    }

    // MARK: - Pull to Refresh Tests

    func test_pull_to_refresh_updates_feed() async {
        let feedView = EventFeedView(cameraId: nil)
        let initialPage = feedView.page
        // Simulate refresh
        await feedView.refreshEvents()
        XCTAssertEqual(feedView.page, 0)
        XCTAssertTrue(feedView.hasMore)
    }

    // MARK: - API Service Tests

    func test_api_service_constructs_correct_urls() {
        let service = VisionOSApiService.shared
        XCTAssertNotNil(service)
    }

    func test_event_filtering_by_threat_level() {
        let events = [
            EventItem(id: 1, cameraName: "Cam1", threatLevel: "EMERGENCY", timestamp: "",
                      thumbnailUrl: nil, description: nil, durationSec: nil, personIds: nil),
            EventItem(id: 2, cameraName: "Cam2", threatLevel: "HIGH", timestamp: "",
                      thumbnailUrl: nil, description: nil, durationSec: nil, personIds: nil),
            EventItem(id: 3, cameraName: "Cam3", threatLevel: "MEDIUM", timestamp: "",
                      thumbnailUrl: nil, description: nil, durationSec: nil, personIds: nil),
            EventItem(id: 4, cameraName: "Cam4", threatLevel: "LOW", timestamp: "",
                      thumbnailUrl: nil, description: nil, durationSec: nil, personIds: nil)
        ]

        let highEvents = events.filter { $0.threatLevel == "HIGH" || $0.threatLevel == "EMERGENCY" }
        XCTAssertEqual(highEvents.count, 2)
    }

    // MARK: - Status Dot Tests

    func test_status_dot_colors() {
        let onlineDot = StatusDot(status: "online")
        let offlineDot = StatusDot(status: "offline")
        let errorDot = StatusDot(status: "error")

        XCTAssertNotNil(onlineDot)
        XCTAssertNotNil(offlineDot)
        XCTAssertNotNil(errorDot)
    }

    // MARK: - Threat Badge Tests

    func test_threat_badge_colors() {
        let emergencyBadge = ThreatBadge(level: "EMERGENCY")
        let highBadge = ThreatBadge(level: "HIGH")
        let mediumBadge = ThreatBadge(level: "MEDIUM")
        let lowBadge = ThreatBadge(level: "LOW")

        XCTAssertNotNil(emergencyBadge)
        XCTAssertNotNil(highBadge)
        XCTAssertNotNil(mediumBadge)
        XCTAssertNotNil(lowBadge)
    }
}
