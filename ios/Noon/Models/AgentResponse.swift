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
    var request: AgentResponseKind { get }
    var metadata: Metadata { get }
}

struct AgentErrorResponse: Codable, Sendable, Error {
    let success: Bool
    let message: String

    init(message: String) {
        self.success = false
        self.message = message
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
            let kind = try container.decode(AgentResponseKind.self, forKey: .request)
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
        case request
    }
}

struct ShowEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: ShowEventMetadata

    typealias Metadata = ShowEventMetadata

    init(metadata: ShowEventMetadata) {
        self.success = true
        self.request = .showEvent
        self.metadata = metadata
    }

    init(success: Bool, metadata: ShowEventMetadata) {
        self.success = success
        self.request = .showEvent
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .showEvent else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'show-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(ShowEventMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

struct ShowScheduleResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: ShowScheduleMetadata

    typealias Metadata = ShowScheduleMetadata

    init(metadata: ShowScheduleMetadata) {
        self.success = true
        self.request = .showSchedule
        self.metadata = metadata
    }

    init(success: Bool, metadata: ShowScheduleMetadata) {
        self.success = success
        self.request = .showSchedule
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .showSchedule else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'show-schedule'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(ShowScheduleMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

struct CreateEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: CreateEventMetadata

    typealias Metadata = CreateEventMetadata

    init(metadata: CreateEventMetadata) {
        self.success = true
        self.request = .createEvent
        self.metadata = metadata
    }

    init(success: Bool, metadata: CreateEventMetadata) {
        self.success = success
        self.request = .createEvent
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .createEvent else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'create-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(CreateEventMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

struct UpdateEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: UpdateEventMetadata

    typealias Metadata = UpdateEventMetadata

    init(metadata: UpdateEventMetadata) {
        self.success = true
        self.request = .updateEvent
        self.metadata = metadata
    }

    init(success: Bool, metadata: UpdateEventMetadata) {
        self.success = success
        self.request = .updateEvent
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .updateEvent else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'update-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(UpdateEventMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

struct DeleteEventResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: DeleteEventMetadata

    typealias Metadata = DeleteEventMetadata

    init(metadata: DeleteEventMetadata) {
        self.success = true
        self.request = .deleteEvent
        self.metadata = metadata
    }

    init(success: Bool, metadata: DeleteEventMetadata) {
        self.success = success
        self.request = .deleteEvent
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .deleteEvent else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'delete-event'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(DeleteEventMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

struct NoActionResponse: AgentSuccessResponse, Codable {
    let success: Bool
    let request: AgentResponseKind
    let metadata: NoActionMetadata

    typealias Metadata = NoActionMetadata

    init(metadata: NoActionMetadata) {
        self.success = true
        self.request = .noAction
        self.metadata = metadata
    }

    init(success: Bool, metadata: NoActionMetadata) {
        self.success = success
        self.request = .noAction
        self.metadata = metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let decodedRequest = try container.decode(AgentResponseKind.self, forKey: .request)
        guard decodedRequest == .noAction else {
            throw DecodingError.dataCorruptedError(forKey: .request, in: container, debugDescription: "Expected request kind 'no-action'.")
        }
        self.success = try container.decode(Bool.self, forKey: .success)
        self.request = decodedRequest
        self.metadata = try container.decode(NoActionMetadata.self, forKey: .metadata)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(request, forKey: .request)
        try container.encode(metadata, forKey: .metadata)
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
        case metadata
    }
}

// MARK: - Metadata

struct ShowEventMetadata: Codable, Sendable {
    let eventID: String
    let calendarID: String

    private enum CodingKeys: String, CodingKey {
        case eventID = "event-id"
        case calendarID = "calendar-id"
    }
}

struct ShowScheduleMetadata: Codable, Sendable {
    let startDateISO: String
    let endDateISO: String

    private enum CodingKeys: String, CodingKey {
        case startDateISO = "start-date"
        case endDateISO = "end-date"
    }
}

struct CreateEventMetadata: Codable, Sendable {
    let payload: [String: AgentJSONValue]

    init(payload: [String: AgentJSONValue]) {
        self.payload = payload
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        self.payload = try container.decode([String: AgentJSONValue].self)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(payload)
    }
}

struct UpdateEventMetadata: Codable, Sendable {
    let eventID: String
    let calendarID: String
    let changes: [String: AgentJSONValue]

    init(eventID: String, calendarID: String, changes: [String: AgentJSONValue]) {
        self.eventID = eventID
        self.calendarID = calendarID
        self.changes = changes
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: DynamicCodingKey.self)

        guard let eventKey = DynamicCodingKey(stringValue: "event-id"),
              let calendarKey = DynamicCodingKey(stringValue: "calendar-id") else {
            throw DecodingError.keyNotFound(DynamicCodingKey(stringValue: "event-id")!, .init(codingPath: decoder.codingPath, debugDescription: "Missing keys for update event metadata"))
        }

        self.eventID = try container.decode(String.self, forKey: eventKey)
        self.calendarID = try container.decode(String.self, forKey: calendarKey)

        var remaining: [String: AgentJSONValue] = [:]
        for key in container.allKeys where key != eventKey && key != calendarKey {
            remaining[key.stringValue] = try container.decode(AgentJSONValue.self, forKey: key)
        }
        self.changes = remaining
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: DynamicCodingKey.self)

        if let eventKey = DynamicCodingKey(stringValue: "event-id") {
            try container.encode(eventID, forKey: eventKey)
        }

        if let calendarKey = DynamicCodingKey(stringValue: "calendar-id") {
            try container.encode(calendarID, forKey: calendarKey)
        }

        for (key, value) in changes {
            if let codingKey = DynamicCodingKey(stringValue: key) {
                try container.encode(value, forKey: codingKey)
            }
        }
    }
}

struct DeleteEventMetadata: Codable, Sendable {
    let eventID: String
    let calendarID: String

    private enum CodingKeys: String, CodingKey {
        case eventID = "event-id"
        case calendarID = "calendar-id"
    }
}

struct NoActionMetadata: Codable, Sendable {
    let reason: String
}

// MARK: - Helpers

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

#if DEBUG
enum AgentMockResponse: CaseIterable, Identifiable {
    case showEvent
    case showSchedule
    case createEvent
    case updateEvent
    case deleteEvent
    case noAction
    case error

    var id: String { rawValue }

    var rawValue: String {
        switch self {
        case .showEvent: return AgentResponseKind.showEvent.rawValue
        case .showSchedule: return AgentResponseKind.showSchedule.rawValue
        case .createEvent: return AgentResponseKind.createEvent.rawValue
        case .updateEvent: return AgentResponseKind.updateEvent.rawValue
        case .deleteEvent: return AgentResponseKind.deleteEvent.rawValue
        case .noAction: return AgentResponseKind.noAction.rawValue
        case .error: return "error"
        }
    }

    var response: AgentResponse {
        switch self {
        case .showEvent:
            return .showEvent(
                ShowEventResponse(
                    metadata: ShowEventMetadata(
                        eventID: "event-123",
                        calendarID: "primary"
                    )
                )
            )
        case .showSchedule:
            return .showSchedule(
                ShowScheduleResponse(
                    metadata: ShowScheduleMetadata(
                        startDateISO: "2025-11-09T10:00:00Z",
                        endDateISO: "2025-11-09T18:00:00Z"
                    )
                )
            )
        case .createEvent:
            return .createEvent(
                CreateEventResponse(
                    metadata: CreateEventMetadata(
                        payload: [
                            "title": .string("Strategy Sync"),
                            "start-time": .string("2025-11-10T15:30:00Z"),
                            "end-time": .string("2025-11-10T16:15:00Z"),
                            "attendees": .array([
                                .string("ashley@example.com"),
                                .string("mike@example.com")
                            ]),
                            "location": .string("Zoom")
                        ]
                    )
                )
            )
        case .updateEvent:
            return .updateEvent(
                UpdateEventResponse(
                    metadata: UpdateEventMetadata(
                        eventID: "event-123",
                        calendarID: "primary",
                        changes: [
                            "title": .string("Updated Strategy Sync"),
                            "notes": .string("Include quarterly OKRs review.")
                        ]
                    )
                )
            )
        case .deleteEvent:
            return .deleteEvent(
                DeleteEventResponse(
                    metadata: DeleteEventMetadata(
                        eventID: "event-123",
                        calendarID: "primary"
                    )
                )
            )
        case .noAction:
            return .noAction(
                NoActionResponse(
                    metadata: NoActionMetadata(
                        reason: "Nothing actionable detected in the last request."
                    )
                )
            )
        case .error:
            return .error(
                AgentErrorResponse(
                    message: "Mock error: Unable to interpret the request."
                )
            )
        }
    }

    var systemImageName: String {
        switch self {
        case .showEvent: return "calendar"
        case .showSchedule: return "calendar.badge.clock"
        case .createEvent: return "calendar.badge.plus"
        case .updateEvent: return "calendar.badge.exclamationmark"
        case .deleteEvent: return "calendar.badge.minus"
        case .noAction: return "zzz"
        case .error: return "exclamationmark.triangle"
        }
    }

    var title: String {
        response.debugTitle
    }

    var subtitle: String {
        response.debugSummary
    }
}

extension AgentResponse {
    static var mockResponses: [AgentMockResponse] {
        AgentMockResponse.allCases
    }

    var debugTitle: String {
        switch self {
        case .showEvent:
            return "Show Event"
        case .showSchedule:
            return "Show Schedule"
        case .createEvent:
            return "Create Event"
        case .updateEvent:
            return "Update Event"
        case .deleteEvent:
            return "Delete Event"
        case .noAction:
            return "No Action"
        case .error:
            return "Error"
        }
    }

    var debugSummary: String {
        switch self {
        case .showEvent(let response):
            return "Open event \"\(response.metadata.eventID)\" on calendar \"\(response.metadata.calendarID)\"."
        case .showSchedule(let response):
            return "Display schedule from \(response.metadata.startDateISO) to \(response.metadata.endDateISO)."
        case .createEvent(let response):
            return "Create event with payload:\n\(Self.jsonString(from: response.metadata.payload))"
        case .updateEvent(let response):
            return """
Update event "\(response.metadata.eventID)" on calendar "\(response.metadata.calendarID)" with changes:
\(Self.jsonString(from: response.metadata.changes))
"""
        case .deleteEvent(let response):
            return "Delete event \"\(response.metadata.eventID)\" on calendar \"\(response.metadata.calendarID)\"."
        case .noAction(let response):
            return "No action taken. Reason: \(response.metadata.reason)"
        case .error(let error):
            return error.message
        }
    }

    var debugIconName: String {
        switch self {
        case .showEvent:
            return "calendar"
        case .showSchedule:
            return "calendar.badge.clock"
        case .createEvent:
            return "calendar.badge.plus"
        case .updateEvent:
            return "calendar.badge.exclamationmark"
        case .deleteEvent:
            return "calendar.badge.minus"
        case .noAction:
            return "zzz"
        case .error:
            return "exclamationmark.triangle"
        }
    }

    private static func jsonString<E: Encodable>(from value: E) -> String {
        do {
            let data = try debugEncoder.encode(value)
            return String(decoding: data, as: UTF8.self)
        } catch {
            return "<unable to encode>"
        }
    }

    private static let debugEncoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .prettyPrinted]
        return encoder
    }()
}
#endif

