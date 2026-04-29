import Foundation
import Alamofire

class VisionOSApiService {
    static let shared = VisionOSApiService()
    private let baseURL = "https://api.visionos.app"
    private let session: Session

    private init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        session = Session(configuration: configuration)
    }

    // MARK: - Events

    func getEvents(cameraId: String? = nil, threatLevel: String? = nil,
                   limit: Int = 20, offset: Int = 0) async throws -> [EventItem] {
        var params: [String: Any] = ["limit": limit, "offset": offset]
        if let cameraId = cameraId { params["camera_id"] = cameraId }
        if let threatLevel = threatLevel { params["threat_level"] = threatLevel }

        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/events", parameters: params)
                .validate()
                .responseDecodable(of: [EventItem].self) { response in
                    switch response.result {
                    case .success(let events):
                        continuation.resume(returning: events)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    func getEventDetail(eventId: Int) async throws -> EventDetail {
        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/events/\(eventId)")
                .validate()
                .responseDecodable(of: EventDetail.self) { response in
                    switch response.result {
                    case .success(let detail):
                        continuation.resume(returning: detail)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Cameras

    func getCameras() async throws -> [CameraSummary] {
        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/cameras")
                .validate()
                .responseDecodable(of: [CameraSummary].self) { response in
                    switch response.result {
                    case .success(let cameras):
                        continuation.resume(returning: cameras)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Persons

    func getPersonProfile(personUid: String) async throws -> PersonProfile {
        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/persons/\(personUid)")
                .validate()
                .responseDecodable(of: PersonProfile.self) { response in
                    switch response.result {
                    case .success(let profile):
                        continuation.resume(returning: profile)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Clips

    func getEventClips(eventId: Int) async throws -> [ClipResult] {
        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/clips/event/\(eventId)")
                .validate()
                .responseDecodable(of: [ClipResult].self) { response in
                    switch response.result {
                    case .success(let clips):
                        continuation.resume(returning: clips)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    func getClipPlaybackUrl(clipId: Int) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            session.request("\(baseURL)/api/clips/\(clipId)/play")
                .validate()
                .responseJSON { response in
                    switch response.result {
                    case .success(let json):
                        if let dict = json as? [String: Any],
                           let url = dict["url"] as? String {
                            continuation.resume(returning: url)
                        } else {
                            continuation.resume(throwing: APIError.invalidResponse)
                        }
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Settings

    func updateUserSettings(_ settings: [String: Any]) async throws {
        _ = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Bool, Error>) in
            session.request("\(baseURL)/api/settings", method: .put, parameters: settings, encoding: JSONEncoding.default)
                .validate()
                .responseJSON { response in
                    switch response.result {
                    case .success:
                        continuation.resume(returning: true)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
        }
    }

    // MARK: - Auth

    func getAuthToken() async throws -> String {
        guard let user = FirebaseAuth.Auth.auth().currentUser else {
            throw APIError.notAuthenticated
        }
        return try await user.getIDToken()
    }
}

enum APIError: LocalizedError {
    case notAuthenticated
    case invalidResponse
    case networkError(String)

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "User is not authenticated"
        case .invalidResponse:
            return "Invalid response from server"
        case .networkError(let message):
            return message
        }
    }
}

// MARK: - Clip Result Model (for API responses)

struct ClipResult: Codable, Identifiable {
    let clipId: Int
    let eventId: Int
    let clipUrl: String
    let thumbnailUrl: String
    let durationSec: Float
    let fileSizeBytes: Int
    let startTimestamp: String
    let endTimestamp: String

    var id: Int { clipId }
}
