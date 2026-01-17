//
//  CalendarService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation
import os

private let calendarLogger = Logger(subsystem: "com.noon.app", category: "CalendarService")

protocol CalendarServicing {
    func fetchCalendars(accessToken: String) async throws -> [GoogleAccount]
    func refreshCalendars(accessToken: String) async throws
    func beginGoogleOAuth(accessToken: String) async throws -> GoogleOAuthStart
    func deleteCalendar(accessToken: String, accountId: String) async throws
    func createEvent(accessToken: String, request: CreateEventRequest) async throws -> CalendarCreateEventResponse
    func deleteEvent(accessToken: String, calendarId: String, eventId: String) async throws
    func fetchEvent(accessToken: String, calendarId: String, eventId: String) async throws -> CalendarEvent
    func updateEvent(accessToken: String, calendarId: String, eventId: String, request: UpdateEventRequest) async throws -> CalendarUpdateEventResponse
}

final class CalendarService: CalendarServicing {
    private let baseURL: URL
    private let urlSession: URLSession

    init(baseURL: URL = CalendarService.defaultBaseURL(), urlSession: URLSession = NetworkSession.shared) {
        self.baseURL = baseURL
        self.urlSession = urlSession
    }

    func fetchCalendars(accessToken: String) async throws -> [GoogleAccount] {
        let request = try makeRequest(path: "/api/v1/calendars/accounts", accessToken: accessToken, method: "GET")
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

    func refreshCalendars(accessToken: String) async throws {
        let request = try makeRequest(path: "/api/v1/calendars/accounts/refresh", accessToken: accessToken, method: "POST")
        do {
            let (_, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when refreshing calendars")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when refreshing calendars")
                    throw CalendarServiceError.unauthorized
                }
                calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when refreshing calendars")
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            calendarLogger.debug("✅ Refreshed calendars from Google API")
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when refreshing calendars: \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func beginGoogleOAuth(accessToken: String) async throws -> GoogleOAuthStart {
        let request = try makeRequest(path: "/api/v1/calendars/accounts/oauth/start", accessToken: accessToken, method: "POST")
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

    func deleteCalendar(accessToken: String, accountId: String) async throws {
        let request = try makeRequest(path: "/api/v1/calendars/accounts/\(accountId)", accessToken: accessToken, method: "DELETE")
        do {
            let (_, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when deleting calendar")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when deleting calendar \(accountId, privacy: .private)")
                    throw CalendarServiceError.unauthorized
                }
                calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when deleting calendar \(accountId, privacy: .private)")
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            calendarLogger.debug("🗑️ Deleted calendar account \(accountId, privacy: .private)")
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when deleting calendar \(accountId, privacy: .private): \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func createEvent(accessToken: String, request: CreateEventRequest) async throws -> CalendarCreateEventResponse {
        var urlRequest = try makeRequest(path: "/api/v1/calendars/events", accessToken: accessToken, method: "POST")
        
        // Encode the request body
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
        urlRequest.httpBody = try encoder.encode(request)
        
        do {
            let (data, response) = try await urlSession.data(for: urlRequest)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when creating event")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when creating event")
                    throw CalendarServiceError.unauthorized
                }
                if let payload = String(data: data, encoding: .utf8) {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when creating event: \(payload, privacy: .private)")
                } else {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when creating event with empty body")
                }
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                decoder.dateDecodingStrategy = .iso8601
                let createResponse = try decoder.decode(CalendarCreateEventResponse.self, from: data)
                calendarLogger.debug("✅ Created event: \(request.summary, privacy: .public)")
                return createResponse
            } catch {
                calendarLogger.error("❌ Decoding error when creating event: \(String(describing: error))")
                throw CalendarServiceError.decoding(error)
            }
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when creating event: \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func deleteEvent(accessToken: String, calendarId: String, eventId: String) async throws {
        var urlComponents = URLComponents(string: "/api/v1/calendars/events/\(eventId)")
        urlComponents?.queryItems = [URLQueryItem(name: "calendar_id", value: calendarId)]
        
        guard let path = urlComponents?.url?.absoluteString else {
            calendarLogger.error("❌ Invalid URL for delete event endpoint")
            throw CalendarServiceError.invalidURL
        }
        
        let request = try makeRequest(path: path, accessToken: accessToken, method: "DELETE")
        
        do {
            let (_, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when deleting event")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when deleting event")
                    throw CalendarServiceError.unauthorized
                }
                calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when deleting event \(eventId, privacy: .private)")
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            calendarLogger.debug("🗑️ Deleted event \(eventId, privacy: .public)")
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when deleting event \(eventId, privacy: .private): \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func fetchEvent(accessToken: String, calendarId: String, eventId: String) async throws -> CalendarEvent {
        let request = try makeRequest(path: "/api/v1/agent/calendars/\(calendarId)/events/\(eventId)", accessToken: accessToken, method: "GET")
        
        do {
            let (data, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when fetching event")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when fetching event")
                    throw CalendarServiceError.unauthorized
                }
                if httpResponse.statusCode == 404 {
                    calendarLogger.error("❌ Event not found: \(eventId, privacy: .private)")
                    throw CalendarServiceError.http(404)
                }
                if let payload = String(data: data, encoding: .utf8) {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching event: \(payload, privacy: .private)")
                } else {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching event with empty body")
                }
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                decoder.dateDecodingStrategy = .iso8601
                let event = try decoder.decode(CalendarEvent.self, from: data)
                calendarLogger.debug("✅ Fetched event: \(eventId, privacy: .public)")
                return event
            } catch {
                calendarLogger.error("❌ Decoding error when fetching event: \(String(describing: error))")
                throw CalendarServiceError.decoding(error)
            }
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when fetching event \(eventId, privacy: .private): \(String(describing: error))")
            throw CalendarServiceError.network(error)
        }
    }

    func updateEvent(accessToken: String, calendarId: String, eventId: String, request: UpdateEventRequest) async throws -> CalendarUpdateEventResponse {
        var urlComponents = URLComponents(string: "/api/v1/calendars/events/\(eventId)")
        urlComponents?.queryItems = [URLQueryItem(name: "calendar_id", value: calendarId)]

        guard let path = urlComponents?.url?.absoluteString else {
            calendarLogger.error("❌ Invalid URL for update event endpoint")
            throw CalendarServiceError.invalidURL
        }

        var urlRequest = try makeRequest(path: path, accessToken: accessToken, method: "PUT")

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.keyEncodingStrategy = .convertToSnakeCase
        urlRequest.httpBody = try encoder.encode(request)

        do {
            let (data, response) = try await urlSession.data(for: urlRequest)
            guard let httpResponse = response as? HTTPURLResponse else {
                calendarLogger.error("❌ Non-HTTP response when updating event")
                throw CalendarServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    calendarLogger.error("🚫 Unauthorized when updating event")
                    throw CalendarServiceError.unauthorized
                }
                if let payload = String(data: data, encoding: .utf8) {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when updating event: \(payload, privacy: .private)")
                } else {
                    calendarLogger.error("❌ HTTP \(httpResponse.statusCode) when updating event with empty body")
                }
                throw CalendarServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                decoder.dateDecodingStrategy = .iso8601
                let updateResponse = try decoder.decode(CalendarUpdateEventResponse.self, from: data)
                calendarLogger.debug("✅ Updated event \(eventId, privacy: .public)")
                return updateResponse
            } catch {
                calendarLogger.error("❌ Decoding error when updating event: \(String(describing: error))")
                throw CalendarServiceError.decoding(error)
            }
        } catch {
            if let calendarError = error as? CalendarServiceError {
                throw calendarError
            }
            calendarLogger.error("❌ Network error when updating event \(eventId, privacy: .private): \(String(describing: error))")
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
        if let override = ProcessInfo.processInfo.environment["BACKEND_URL"], let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}

