//
//  CalendarService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation
import os

private let calendarLogger = Logger(subsystem: "com.noon.app", category: "CalendarService")

struct GoogleAccount: Identifiable, Decodable, Hashable {
    let id: String
    let userId: String
    let googleUserId: String
    let email: String
    let displayName: String?
    let avatarURL: String?
    let createdAt: Date
    let updatedAt: Date

    private enum CodingKeys: String, CodingKey {
        case id
        case userId
        case googleUserId
        case email
        case displayName
        case avatarURL
        case createdAt
        case updatedAt
    }

    private enum LegacyCodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case googleUserId = "google_user_id"
        case email
        case displayName = "display_name"
        case avatarURL = "avatar_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    init(id: String,
         userId: String,
         googleUserId: String,
         email: String,
         displayName: String?,
         avatarURL: String?,
         createdAt: Date,
         updatedAt: Date) {
        self.id = id
        self.userId = userId
        self.googleUserId = googleUserId
        self.email = email
        self.displayName = displayName
        self.avatarURL = avatarURL
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    init(from decoder: Decoder) throws {
        let camel = try decoder.container(keyedBy: CodingKeys.self)
        let snake = try decoder.container(keyedBy: LegacyCodingKeys.self)

        func decodeRequired<T: Decodable>(_ type: T.Type, camelKey: CodingKeys, snakeKey: LegacyCodingKeys) throws -> T {
            if let value = try camel.decodeIfPresent(type, forKey: camelKey) {
                return value
            }
            if let value = try snake.decodeIfPresent(type, forKey: snakeKey) {
                return value
            }
            let description = "Missing required key \"\(snakeKey.rawValue)\" or \"\(camelKey.rawValue)\" when decoding GoogleAccount."
            throw DecodingError.keyNotFound(
                snakeKey,
                DecodingError.Context(codingPath: decoder.codingPath, debugDescription: description)
            )
        }

        func decodeOptional<T: Decodable>(_ type: T.Type, camelKey: CodingKeys, snakeKey: LegacyCodingKeys) throws -> T? {
            if let value = try camel.decodeIfPresent(type, forKey: camelKey) {
                return value
            }
            return try snake.decodeIfPresent(type, forKey: snakeKey)
        }

        self.id = try decodeRequired(String.self, camelKey: .id, snakeKey: .id)
        self.userId = try decodeRequired(String.self, camelKey: .userId, snakeKey: .userId)
        self.googleUserId = try decodeRequired(String.self, camelKey: .googleUserId, snakeKey: .googleUserId)
        self.email = try decodeRequired(String.self, camelKey: .email, snakeKey: .email)
        self.displayName = try decodeOptional(String.self, camelKey: .displayName, snakeKey: .displayName)
        self.avatarURL = try decodeOptional(String.self, camelKey: .avatarURL, snakeKey: .avatarURL)
        self.createdAt = try decodeRequired(Date.self, camelKey: .createdAt, snakeKey: .createdAt)
        self.updatedAt = try decodeRequired(Date.self, camelKey: .updatedAt, snakeKey: .updatedAt)
    }
}

enum CalendarServiceError: Error {
    case invalidURL
    case unauthorized
    case http(Int)
    case decoding(Error)
    case network(Error)
    case unexpectedResponse
}

protocol CalendarServicing {
    func fetchCalendars(accessToken: String) async throws -> [GoogleAccount]
    func beginGoogleOAuth(accessToken: String) async throws -> GoogleOAuthStart
}

struct GoogleOAuthStart: Decodable {
    let authorizationURL: URL
    let state: String
    let stateExpiresAt: Date

    private enum CodingKeys: String, CodingKey {
        case authorizationURL = "authorization_url"
        case state
        case stateExpiresAt = "state_expires_at"
    }
}

final class CalendarService: CalendarServicing {
    private let baseURL: URL
    private let urlSession: URLSession

    init(baseURL: URL = CalendarService.defaultBaseURL(), urlSession: URLSession = .shared) {
        self.baseURL = baseURL
        self.urlSession = urlSession
    }

    func fetchCalendars(accessToken: String) async throws -> [GoogleAccount] {
        let request = try makeRequest(path: "/google-accounts/", accessToken: accessToken, method: "GET")
        do {
            let (data, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when fetching calendars")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when fetching calendars")
                    throw CalendarServiceError.unauthorized
                }
                if let payload = String(data: data, encoding: .utf8) {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching calendars: \(payload, privacy: .private)")
                } else {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching calendars with empty body")
                }
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                decoder.dateDecodingStrategy = .iso8601
                let accounts = try decoder.decode([GoogleAccount].self, from: data)
                calendarLogger.debug("✅ Loaded \(accounts.count, privacy: .public) calendars")
                return accounts
            } catch {
                calendarLogger.error("❌ Decoding error when fetching calendars: \(String(describing: error))")
                throw CalendarServiceError.decoding(error)
            }
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when fetching calendars: \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func beginGoogleOAuth(accessToken: String) async throws -> GoogleOAuthStart {
        let request = try makeRequest(path: "/google-accounts/oauth/start", accessToken: accessToken, method: "POST")
        do {
            let (data, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when preparing Google OAuth")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when starting Google OAuth")
                    throw CalendarServiceError.unauthorized
                }
                if let payload = String(data: data, encoding: .utf8) {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when starting Google OAuth: \(payload, privacy: .private)")
                }
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                let start = try decoder.decode(GoogleOAuthStart.self, from: data)
                calendarLogger.debug("✅ Received Google OAuth URL with state that expires at \(start.stateExpiresAt.timeIntervalSince1970, privacy: .public)")
                return start
            } catch {
                calendarLogger.error("❌ Decoding error when starting Google OAuth: \(String(describing: error))")
                throw CalendarServiceError.decoding(error)
            }
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when starting Google OAuth: \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }
}

private extension CalendarService {
    func makeRequest(path: String, accessToken: String, method: String) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            calendarLogger.error("❌ Invalid URL for calendars endpoint: \(path, privacy: .public)")
            throw CalendarServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        if method != "GET" {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = Data()
        }
        return request
    }

    static func defaultBaseURL() -> URL {
        if let override = ProcessInfo.processInfo.environment["NOON_BACKEND_URL"], let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}

