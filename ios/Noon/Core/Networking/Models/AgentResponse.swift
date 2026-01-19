//
//  AgentResponse.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

enum AgentResponseKind: String, Codable, Sendable {
    case showEvent = "show-event"
    case showSchedule = "show-schedule"
    case createEvent = "create-event"
    case updateEvent = "update-event"
    case deleteEvent = "delete-event"
    case noAction = "no-action"
}

@preconcurrency protocol AgentSuccessResponse: Sendable {
    associatedtype Metadata: Sendable
    var success: Bool { get }
    var type: AgentResponseKind { get }
    var metadata: Metadata { get }
}

struct AgentErrorResponse: Codable, Sendable, Error {
    let success: Bool
    let message: String
    let query: String?

    init(message: String, query: String? = nil) {
        self.success = false
        self.message = message
        self.query = query
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.success = try container.decode(Bool.self, forKey: .success)
        self.message = try container.decode(String.self, forKey: .message)
        self.query = try container.decodeIfPresent(String.self, forKey: .query)
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(message, forKey: .message)
        try container.encodeIfPresent(query, forKey: .query)
    }
    
    private enum CodingKeys: String, CodingKey {
        case success
        case message
        case query
    }
}

enum AgentResponse: Codable, Sendable {
    case showEvent(ShowEventResponse)
    case showSchedule(ShowScheduleResponse)
    case createEvent(CreateEventResponse)
    case updateEvent(UpdateEventResponse)
    case deleteEvent(DeleteEventResponse)
    case noAction(NoActionResponse)
    case error(AgentErrorResponse)

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let success = try container.decode(Bool.self, forKey: .success)

        if success {
            let kind = try container.decode(AgentResponseKind.self, forKey: .type)
            switch kind {
            case .showEvent:
                self = .showEvent(try ShowEventResponse(from: decoder))
            case .showSchedule:
                self = .showSchedule(try ShowScheduleResponse(from: decoder))
            case .createEvent:
                self = .createEvent(try CreateEventResponse(from: decoder))
            case .updateEvent:
                self = .updateEvent(try UpdateEventResponse(from: decoder))
            case .deleteEvent:
                self = .deleteEvent(try DeleteEventResponse(from: decoder))
            case .noAction:
                self = .noAction(try NoActionResponse(from: decoder))
            }
        } else {
            self = .error(try AgentErrorResponse(from: decoder))
        }
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .showEvent(let response):
            try response.encode(to: encoder)
        case .showSchedule(let response):
            try response.encode(to: encoder)
        case .createEvent(let response):
            try response.encode(to: encoder)
        case .updateEvent(let response):
            try response.encode(to: encoder)
        case .deleteEvent(let response):
            try response.encode(to: encoder)
        case .noAction(let response):
            try response.encode(to: encoder)
        case .error(let error):
            try error.encode(to: encoder)
        }
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
    }
    
    var typeString: String {
        switch self {
        case .showEvent: return "show-event"
        case .showSchedule: return "show-schedule"
        case .createEvent: return "create-event"
        case .updateEvent: return "update-event"
        case .deleteEvent: return "delete-event"
        case .noAction: return "no-action"
        case .error: return "error"
        }
    }
}

struct ShowEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: ShowEventMetadata
    let query: String

    typealias Metadata = ShowEventMetadata

    init(metadata: ShowEventMetadata, query: String) {
        self.success = true
        self.type = .showEvent
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: ShowEventMetadata, query: String) {
        self.success = success
        self.type = .showEvent
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .showEvent else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'show-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(ShowEventMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

struct ShowScheduleResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: ShowScheduleMetadata
    let query: String

    typealias Metadata = ShowScheduleMetadata

    init(metadata: ShowScheduleMetadata, query: String) {
        self.success = true
        self.type = .showSchedule
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: ShowScheduleMetadata, query: String) {
        self.success = success
        self.type = .showSchedule
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .showSchedule else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'show-schedule'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(ShowScheduleMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

struct CreateEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: CreateEventMetadata
    let query: String

    typealias Metadata = CreateEventMetadata

    init(metadata: CreateEventMetadata, query: String) {
        self.success = true
        self.type = .createEvent
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: CreateEventMetadata, query: String) {
        self.success = success
        self.type = .createEvent
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .createEvent else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'create-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(CreateEventMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

struct UpdateEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: UpdateEventMetadata
    let query: String

    typealias Metadata = UpdateEventMetadata

    init(metadata: UpdateEventMetadata, query: String) {
        self.success = true
        self.type = .updateEvent
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: UpdateEventMetadata, query: String) {
        self.success = success
        self.type = .updateEvent
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .updateEvent else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'update-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(UpdateEventMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

struct DeleteEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: DeleteEventMetadata
    let query: String

    typealias Metadata = DeleteEventMetadata

    init(metadata: DeleteEventMetadata, query: String) {
        self.success = true
        self.type = .deleteEvent
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: DeleteEventMetadata, query: String) {
        self.success = success
        self.type = .deleteEvent
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .deleteEvent else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'delete-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(DeleteEventMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

struct NoActionResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let type: AgentResponseKind
    let metadata: NoActionMetadata
    let query: String

    typealias Metadata = NoActionMetadata

    init(metadata: NoActionMetadata, query: String) {
        self.success = true
        self.type = .noAction
        self.metadata = metadata
        self.query = query
    }

    init(success: Bool, metadata: NoActionMetadata, query: String) {
        self.success = success
        self.type = .noAction
        self.metadata = metadata
        self.query = query
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedType = try container.decode(AgentResponseKind.self, forKey: .type)
        guard decodedType == .noAction else {
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Expected type 'no-action'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.type = decodedType
        self.metadata = try container.decode(NoActionMetadata.self, forKey: .metadata)
        self.query = try container.decode(String.self, forKey: .query)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(type, forKey: .type)
        try container.encode(metadata, forKey: .metadata)
        try container.encode(query, forKey: .query)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case type
        case metadata
        case query
    }
}

// MARK: - Metadata

struct ShowEventMetadata: Codable, Sendable {
    let event_id: String
    let calendar_id: String

    private enum CodingKeys: String, CodingKey {
        case event_id
        case calendar_id
    }
}

struct ShowScheduleMetadata: Codable, Sendable {
    let start_date: String
    let end_date: String

    private enum CodingKeys: String, CodingKey {
        case start_date
        case end_date
    }
}

struct CreateEventMetadata: Codable, Sendable {
    let summary: String
    let start: DateTimeDict
    let end: DateTimeDict
    let calendar_id: String
    let description: String?
    let location: String?

    private enum CodingKeys: String, CodingKey {
        case summary
        case start
        case end
        case calendar_id
        case description
        case location
    }
}

struct UpdateEventMetadata: Codable, Sendable {
    let event_id: String
    let calendar_id: String
    let summary: String?
    let start: DateTimeDict?
    let end: DateTimeDict?
    let description: String?
    let location: String?

    private enum CodingKeys: String, CodingKey {
        case event_id
        case calendar_id
        case summary
        case start
        case end
        case description
        case location
    }
}

struct DeleteEventMetadata: Codable, Sendable {
    let event_id: String
    let calendar_id: String

    private enum CodingKeys: String, CodingKey {
        case event_id
        case calendar_id
    }
}

struct NoActionMetadata: Codable, Sendable {
    let reason: String
}

// MARK: - Helpers

enum DateTimeDict: Codable, Sendable {
    case timed(dateTime: Date)
    case allDay(date: String)
    
    // Computed property to convert date string to Date for convenience
    var dateAsDate: Date? {
        if case .allDay(let dateString) = self {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(secondsFromGMT: 0)
            formatter.calendar = Calendar(identifier: .gregorian)
            formatter.locale = Locale(identifier: "en_US_POSIX")
            return formatter.date(from: dateString)
        }
        return nil
    }
    
    // Check if this represents an all-day event
    var isAllDay: Bool {
        if case .allDay = self {
            return true
        }
        return false
    }
    
    var dateTime: Date? {
        if case .timed(let dateTime) = self {
            return dateTime
        }
        return nil
    }
    
    var date: String? {
        if case .allDay(let date) = self {
            return date
        }
        return nil
    }
    
    init(dateTime: Date) {
        self = .timed(dateTime: dateTime)
    }
    
    init(date: String) {
        self = .allDay(date: date)
    }
    
    init(dateTime: Date? = nil, date: String? = nil) {
        if let dateTime = dateTime {
            self = .timed(dateTime: dateTime)
        } else if let date = date {
            self = .allDay(date: date)
        } else {
            // Default to all-day with today's date if nothing provided (shouldn't happen in practice)
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            formatter.timeZone = TimeZone(secondsFromGMT: 0)
            self = .allDay(date: formatter.string(from: Date()))
        }
    }
    
    enum CodingKeys: String, CodingKey {
        case dateTime
        case date
        case type
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // Check if we have dateTime (timed) or date (all-day)
        if let dateTimeString = try? container.decode(String.self, forKey: .dateTime) {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let dateTime = formatter.date(from: dateTimeString) ?? ISO8601DateFormatter().date(from: dateTimeString) {
                self = .timed(dateTime: dateTime)
            } else {
                throw DecodingError.dataCorruptedError(
                    forKey: .dateTime,
                    in: container,
                    debugDescription: "Unable to parse dateTime string: \(dateTimeString)"
                )
            }
        } else if let dateString = try? container.decode(String.self, forKey: .date) {
            self = .allDay(date: dateString)
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: decoder.codingPath,
                    debugDescription: "DateTimeDict must have either dateTime or date field"
                )
            )
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .timed(let dateTime):
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            try container.encode(formatter.string(from: dateTime), forKey: .dateTime)
        case .allDay(let date):
            try container.encode(date, forKey: .date)
        }
    }
}

struct DynamicCodingKey: CodingKey, Hashable {
    var stringValue: String
    var intValue: Int? { nil }

    init?(stringValue: String) {
        self.stringValue = stringValue
    }

    init?(intValue: Int) {
        nil
    }
}

enum AgentJSONValue: Codable, Hashable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: AgentJSONValue])
    case array([AgentJSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if container.decodeNil() {
            self = .null
            return
        }

        if let boolValue = try? container.decode(Bool.self) {
            self = .bool(boolValue)
            return
        }

        if let doubleValue = try? container.decode(Double.self) {
            self = .number(doubleValue)
            return
        }

        if let stringValue = try? container.decode(String.self) {
            self = .string(stringValue)
            return
        }

        if let arrayValue = try? container.decode([AgentJSONValue].self) {
            self = .array(arrayValue)
            return
        }

        if let objectValue = try? container.decode([String: AgentJSONValue].self) {
            self = .object(objectValue)
            return
        }

        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }
}

