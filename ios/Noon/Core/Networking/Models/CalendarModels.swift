//
//  CalendarModels.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import Foundation

struct GoogleAccount: Identifiable, Decodable, Hashable {
    let id: String
    let userId: String
    let googleUserId: String
    let email: String
    let displayName: String?
    let avatarURL: String?
    let createdAt: Date
    let updatedAt: Date
    let calendars: [GoogleCalendar]?

    private enum CodingKeys: String, CodingKey {
        case id
        case userId
        case googleUserId
        case email
        case displayName
        case avatarURL
        case createdAt
        case updatedAt
        case calendars
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
        case calendars
    }

    init(id: String,
         userId: String,
         googleUserId: String,
         email: String,
         displayName: String?,
         avatarURL: String?,
         createdAt: Date,
         updatedAt: Date,
         calendars: [GoogleCalendar]? = nil) {
        self.id = id
        self.userId = userId
        self.googleUserId = googleUserId
        self.email = email
        self.displayName = displayName
        self.avatarURL = avatarURL
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.calendars = calendars
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
        
        // Decode calendars - try camelCase first, then snake_case
        if let camelCalendars = try? camel.decodeIfPresent([GoogleCalendar].self, forKey: .calendars) {
            self.calendars = camelCalendars
        } else if let snakeCalendars = try? snake.decodeIfPresent([GoogleCalendar].self, forKey: .calendars) {
            self.calendars = snakeCalendars
        } else {
            self.calendars = nil
        }
    }
}

struct GoogleCalendar: Identifiable, Decodable, Hashable {
    let id: String
    let googleCalendarId: String
    let name: String
    let description: String?
    let color: String?
    let isPrimary: Bool
    let googleAccountId: String
    let createdAt: Date
    let updatedAt: Date

    init(id: String,
         googleCalendarId: String,
         name: String,
         description: String?,
         color: String?,
         isPrimary: Bool,
         googleAccountId: String,
         createdAt: Date,
         updatedAt: Date) {
        self.id = id
        self.googleCalendarId = googleCalendarId
        self.name = name
        self.description = description
        self.color = color
        self.isPrimary = isPrimary
        self.googleAccountId = googleAccountId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
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
            formatter.calendar = Foundation.Calendar(identifier: .gregorian)
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

enum CalendarServiceError: Error {
    case invalidURL
    case unauthorized
    case http(Int)
    case decoding(Error)
    case network(Error)
    case unexpectedResponse
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

// Backend EventTime union type (matches backend TimedEventTime/AllDayEventTime)
struct BackendEventTime: Encodable {
    enum EventTimeType: String, Codable {
        case timed
        case allDay = "all_day"
    }
    
    let type: EventTimeType
    let dateTime: Date?
    let date: String?
    let timeZone: String?
    
    init(timed dateTime: Date, timeZone: String?) {
        self.type = .timed
        self.dateTime = dateTime
        self.date = nil
        self.timeZone = timeZone
    }
    
    init(allDay date: String) {
        self.type = .allDay
        self.dateTime = nil
        self.date = date
        self.timeZone = nil
    }
    
    enum CodingKeys: String, CodingKey {
        case type
        case dateTime
        case date
        case timeZone
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        
        switch type {
        case .timed:
            if let dateTime = dateTime {
                let formatter = ISO8601DateFormatter()
                formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                try container.encode(formatter.string(from: dateTime), forKey: .dateTime)
            }
            if let timeZone = timeZone {
                try container.encode(timeZone, forKey: .timeZone)
            }
        case .allDay:
            if let date = date {
                try container.encode(date, forKey: .date)
            }
        }
    }
}

struct CreateEventRequest: Encodable {
    let summary: String
    let start: BackendEventTime
    let end: BackendEventTime
    let calendarId: String
    let description: String?
    let location: String?
    let timezone: String

    enum CodingKeys: String, CodingKey {
        case summary
        case start
        case end
        case calendarId = "calendar_id"
        case description
        case location
        case timezone
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        try container.encode(summary, forKey: .summary)
        try container.encode(start, forKey: .start)
        try container.encode(end, forKey: .end)
        try container.encode(calendarId, forKey: .calendarId)
        try container.encode(timezone, forKey: .timezone)
        
        // Encode optional fields
        if let description = description {
            try container.encode(description, forKey: .description)
        }
        if let location = location {
            try container.encode(location, forKey: .location)
        }
    }
}

struct CalendarCreateEventResponse: Decodable {
    let event: CalendarEvent
}

struct UpdateEventRequest: Encodable {
    let summary: String?
    let start: BackendEventTime?
    let end: BackendEventTime?
    let calendarId: String
    let description: String?
    let location: String?
    let timezone: String

    enum CodingKeys: String, CodingKey {
        case summary
        case start
        case end
        case calendarId = "calendar_id"
        case description
        case location
        case timezone
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        
        // Only encode non-nil optional values
        if let summary = summary {
            try container.encode(summary, forKey: .summary)
        }
        if let start = start {
            try container.encode(start, forKey: .start)
        }
        if let end = end {
            try container.encode(end, forKey: .end)
        }
        // Always encode required fields
        try container.encode(calendarId, forKey: .calendarId)
        if let description = description {
            try container.encode(description, forKey: .description)
        }
        if let location = location {
            try container.encode(location, forKey: .location)
        }
        try container.encode(timezone, forKey: .timezone)
    }
}

struct CalendarUpdateEventResponse: Decodable {
    let event: CalendarEvent
}
