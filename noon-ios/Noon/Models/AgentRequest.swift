//
//  AgentRequest.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

enum AgentRequestKind: String, Codable, Sendable {
    case showEvent = "show-event"
    case showSchedule = "show-schedule"
    case createEvent = "create-event"
    case updateEvent = "update-event"
    case deleteEvent = "delete-event"
    case noAction = "no-action"
}

protocol AgentSuccessRequest: Codable, Sendable {
    associatedtype Metadata: Codable & Sendable
    var success: Bool { get }
    var request: AgentRequestKind { get }
    var metadata: Metadata { get }
}

struct AgentRequestError: Codable, Sendable, Error {
    let success: Bool
    let message: String?

    init(message: String?) {
        self.success = false
        self.message = message
    }
}

enum AgentRequest: Codable, Sendable {
    case showEvent(ShowEventRequest)
    case showSchedule(ShowScheduleRequest)
    case createEvent(CreateEventRequest)
    case updateEvent(UpdateEventRequest)
    case deleteEvent(DeleteEventRequest)
    case noAction(NothingRequest)
    case failure(AgentRequestError)

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let success = try container.decode(Bool.self, forKey: .success)

        if success {
            let kind = try container.decode(AgentRequestKind.self, forKey: .request)
            switch kind {
            case .showEvent:
                self = .showEvent(try ShowEventRequest(from: decoder))
            case .showSchedule:
                self = .showSchedule(try ShowScheduleRequest(from: decoder))
            case .createEvent:
                self = .createEvent(try CreateEventRequest(from: decoder))
            case .updateEvent:
                self = .updateEvent(try UpdateEventRequest(from: decoder))
            case .deleteEvent:
                self = .deleteEvent(try DeleteEventRequest(from: decoder))
            case .noAction:
                self = .noAction(try NothingRequest(from: decoder))
            }
        } else {
            self = .failure(try AgentRequestError(from: decoder))
        }
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .showEvent(let request):
            try request.encode(to: encoder)
        case .showSchedule(let request):
            try request.encode(to: encoder)
        case .createEvent(let request):
            try request.encode(to: encoder)
        case .updateEvent(let request):
            try request.encode(to: encoder)
        case .deleteEvent(let request):
            try request.encode(to: encoder)
        case .noAction(let request):
            try request.encode(to: encoder)
        case .failure(let error):
            try error.encode(to: encoder)
        }
    }

    private enum CodingKeys: String, CodingKey {
        case success
        case request
    }
}

struct ShowEventRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: ShowEventMetadata

    init(metadata: ShowEventMetadata) {
        self.success = true
        self.request = .showEvent
        self.metadata = metadata
    }
}

struct ShowScheduleRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: ShowScheduleMetadata

    init(metadata: ShowScheduleMetadata) {
        self.success = true
        self.request = .showSchedule
        self.metadata = metadata
    }
}

struct CreateEventRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: CreateEventMetadata

    init(metadata: CreateEventMetadata) {
        self.success = true
        self.request = .createEvent
        self.metadata = metadata
    }
}

struct UpdateEventRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: UpdateEventMetadata

    init(metadata: UpdateEventMetadata) {
        self.success = true
        self.request = .updateEvent
        self.metadata = metadata
    }
}

struct DeleteEventRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: DeleteEventMetadata

    init(metadata: DeleteEventMetadata) {
        self.success = true
        self.request = .deleteEvent
        self.metadata = metadata
    }
}

struct NothingRequest: AgentSuccessRequest {
    let success: Bool
    let request: AgentRequestKind
    let metadata: NothingMetadata

    init(metadata: NothingMetadata) {
        self.success = true
        self.request = .noAction
        self.metadata = metadata
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

        guard let eventKey = DynamicCodingKey("event-id"),
              let calendarKey = DynamicCodingKey("calendar-id") else {
            throw DecodingError.keyNotFound(DynamicCodingKey("event-id")!, .init(codingPath: decoder.codingPath, debugDescription: "Missing keys for update event metadata"))
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

        if let eventKey = DynamicCodingKey("event-id") {
            try container.encode(eventID, forKey: eventKey)
        }

        if let calendarKey = DynamicCodingKey("calendar-id") {
            try container.encode(calendarID, forKey: calendarKey)
        }

        for (key, value) in changes {
            if let codingKey = DynamicCodingKey(key) {
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

struct NothingMetadata: Codable, Sendable {
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
        return nil
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

