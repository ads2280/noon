//
//  GoogleCalendarService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/12/25.
//

import Foundation
import os

private let googleCalendarLogger = Logger(subsystem: "com.noon.app", category: "GoogleCalendarService")

struct GoogleCalendarSchedule: Decodable, Sendable {
    struct Window: Decodable, Sendable {
        let start: Date
        let end: Date
        let timezone: String
        let startDate: Date
        let endDate: Date

        private enum CodingKeys: String, CodingKey {
            case start
            case end
            case timezone
            case startDate = "start_date"
            case endDate = "end_date"
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            
            // Try to decode datetime fields as Date (works with JSONDecoder's .iso8601 strategy)
            let parsedStart: Date
            let parsedEnd: Date
            
            if let directStart = try? container.decode(Date.self, forKey: .start),
               let directEnd = try? container.decode(Date.self, forKey: .end) {
                parsedStart = directStart
                parsedEnd = directEnd
            } else {
                // Fall back to string parsing for datetime fields
                let startString = try container.decode(String.self, forKey: .start)
                let endString = try container.decode(String.self, forKey: .end)
                
                guard let parsedStartValue = Window.dateTimeFormatter.date(from: startString) ??
                                         ISO8601DateFormatter().date(from: startString),
                      let parsedEndValue = Window.dateTimeFormatter.date(from: endString) ??
                                      ISO8601DateFormatter().date(from: endString) else {
                    throw DecodingError.dataCorruptedError(
                        forKey: .start,
                        in: container,
                        debugDescription: "Unable to parse schedule window start/end dates. Start: \(startString), End: \(endString)"
                    )
                }
                
                parsedStart = parsedStartValue
                parsedEnd = parsedEndValue
            }
            
            self.start = parsedStart
            self.end = parsedEnd
            self.timezone = try container.decode(String.self, forKey: .timezone)
            
            // Try to decode date-only fields as Date first, then fall back to string parsing
            if let directStartDate = try? container.decode(Date.self, forKey: .startDate),
               let directEndDate = try? container.decode(Date.self, forKey: .endDate) {
                self.startDate = directStartDate
                self.endDate = directEndDate
            } else {
                // Fall back to string parsing for date-only fields
                let startDateString = try container.decode(String.self, forKey: .startDate)
                let endDateString = try container.decode(String.self, forKey: .endDate)
                
                guard let parsedStartDate = Window.dateFormatter.date(from: startDateString),
                      let parsedEndDate = Window.dateFormatter.date(from: endDateString) else {
                    throw DecodingError.dataCorruptedError(
                        forKey: .startDate,
                        in: container,
                        debugDescription: "Unable to parse schedule window start/end date values. StartDate: \(startDateString), EndDate: \(endDateString)"
                    )
                }
                
                self.startDate = parsedStartDate
                self.endDate = parsedEndDate
            }
        }

        private static let dateTimeFormatter: ISO8601DateFormatter = {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [
                .withInternetDateTime,
                .withFractionalSeconds
            ]
            return formatter
        }()

        private static let dateFormatter: DateFormatter = {
            let formatter = DateFormatter()
            formatter.calendar = Calendar(identifier: .gregorian)
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone(secondsFromGMT: 0)
            formatter.dateFormat = "yyyy-MM-dd"
            return formatter
        }()
    }

    let window: Window
    let events: [CalendarEvent]
    
    enum CodingKeys: String, CodingKey {
        case window
        case events
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.window = try container.decode(Window.self, forKey: .window)
        self.events = try container.decode([CalendarEvent].self, forKey: .events)
    }
}

enum GoogleCalendarScheduleServiceError: LocalizedError {
    case invalidURL
    case unauthorized
    case http(Int)
    case decoding(Error)
    case network(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "We couldn't reach the calendar service."
        case .unauthorized:
            return "We weren't able to access your Google Calendar. Please reconnect and try again."
        case .http(let statusCode):
            return "Calendar service responded with status code \(statusCode)."
        case .decoding:
            return "We couldn't understand the calendar data returned by the server."
        case .network:
            return "The calendar request failed. Check your connection and try again."
        }
    }
}

protocol GoogleCalendarScheduleServicing: Sendable {
    func fetchSchedule(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> GoogleCalendarSchedule
}

final class GoogleCalendarScheduleService: GoogleCalendarScheduleServicing {
    private let baseURL: URL
    private let urlSession: URLSession

    init(baseURL: URL = GoogleCalendarScheduleService.defaultBaseURL(), urlSession: URLSession = .shared) {
        self.baseURL = baseURL
        self.urlSession = urlSession
    }

    func fetchSchedule(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> GoogleCalendarSchedule {
        var request = try makeRequest(accessToken: accessToken)
        let payload = ScheduleRequestPayload(
            startDate: startDateISO,
            endDate: endDateISO
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.withoutEscapingSlashes]
        request.httpBody = try encoder.encode(payload)

        do {
            let (data, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                googleCalendarLogger.error("❌ Non-HTTP response when fetching schedule.")
                throw GoogleCalendarScheduleServiceError.http(-1)
            }

            guard 200..<300 ~= httpResponse.statusCode else {
                if httpResponse.statusCode == 401 {
                    googleCalendarLogger.error("🚫 Unauthorized when fetching schedule.")
                    throw GoogleCalendarScheduleServiceError.unauthorized
                }

                if let payloadString = String(data: data, encoding: .utf8) {
                    googleCalendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching schedule: \(payloadString, privacy: .private)")
                } else {
                    googleCalendarLogger.error("❌ HTTP \(httpResponse.statusCode) when fetching schedule with empty body.")
                }
                throw GoogleCalendarScheduleServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                let schedule = try decoder.decode(GoogleCalendarSchedule.self, from: data)
                googleCalendarLogger.debug("✅ Loaded schedule with \(schedule.events.count, privacy: .public) events.")
                return schedule
            } catch {
                if let dataString = String(data: data, encoding: .utf8) {
                    googleCalendarLogger.error("❌ Decoding schedule failed: \(String(describing: error)). Response: \(dataString, privacy: .private)")
                } else {
                    googleCalendarLogger.error("❌ Decoding schedule failed: \(String(describing: error))")
                }
                throw GoogleCalendarScheduleServiceError.decoding(error)
            }
        } catch {
            if let knownError = error as? GoogleCalendarScheduleServiceError {
                throw knownError
            }
            googleCalendarLogger.error("❌ Network error when fetching schedule: \(String(describing: error))")
            throw GoogleCalendarScheduleServiceError.network(error)
        }
    }
}

private extension GoogleCalendarScheduleService {
    struct ScheduleRequestPayload: Encodable {
        let startDate: String
        let endDate: String

        enum CodingKeys: String, CodingKey {
            case startDate = "start_date"
            case endDate = "end_date"
        }
    }

    func makeRequest(accessToken: String) throws -> URLRequest {
        guard let url = URL(string: "/google-calendar/schedule", relativeTo: baseURL) else {
            throw GoogleCalendarScheduleServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        return request
    }

    static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    static let iso8601Formatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = .autoupdatingCurrent
        formatter.formatOptions = [
            .withInternetDateTime,
            .withFractionalSeconds
        ]
        return formatter
    }()

    static func defaultBaseURL() -> URL {
        if let override = ProcessInfo.processInfo.environment["NOON_BACKEND_URL"],
           let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}


