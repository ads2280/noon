//
//  GoogleCalendarService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/12/25.
//

import Foundation
import os

private let googleCalendarLogger = Logger(subsystem: "com.noon.app", category: "GoogleCalendarService")

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

    init(baseURL: URL = GoogleCalendarScheduleService.defaultBaseURL(), urlSession: URLSession = NetworkSession.shared) {
        self.baseURL = baseURL
        self.urlSession = urlSession
    }

    func fetchSchedule(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> GoogleCalendarSchedule {
        let totalStart = Date()
        await TimingLogger.shared.logStart("frontend.google_calendar_service.fetch_schedule", details: "start_date=\(startDateISO) end_date=\(endDateISO)")
        
        // Request preparation
        let prepStart = Date()
        var request = try makeRequest(accessToken: accessToken)
        let payload = ScheduleRequestPayload(
            startDate: startDateISO,
            endDate: endDateISO
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.withoutEscapingSlashes]
        request.httpBody = try encoder.encode(payload)
        let prepDuration = Date().timeIntervalSince(prepStart)
        await TimingLogger.shared.logStep("frontend.google_calendar_service.fetch_schedule.prepare_request", duration: prepDuration)

        do {
            // Network call
            let networkStart = Date()
            let (data, response) = try await urlSession.data(for: request)
            let networkDuration = Date().timeIntervalSince(networkStart)
            await TimingLogger.shared.logStep("frontend.google_calendar_service.fetch_schedule.network", duration: networkDuration, details: "data_size=\(data.count) bytes")
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
                // Decoding
                let decodeStart = Date()
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                // Note: Not using convertFromSnakeCase because Window and CalendarEvent use explicit CodingKeys mappings
                
                let schedule = try decoder.decode(GoogleCalendarSchedule.self, from: data)
                let decodeDuration = Date().timeIntervalSince(decodeStart)
                await TimingLogger.shared.logStep("frontend.google_calendar_service.fetch_schedule.decode", duration: decodeDuration, details: "event_count=\(schedule.events.count)")
                
                let totalDuration = Date().timeIntervalSince(totalStart)
                await TimingLogger.shared.logStep("frontend.google_calendar_service.fetch_schedule", duration: totalDuration, details: "event_count=\(schedule.events.count)")
                
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
        guard let url = URL(string: "/api/v1/calendars/schedule", relativeTo: baseURL) else {
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
        if let override = ProcessInfo.processInfo.environment["BACKEND_URL"],
           let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}


