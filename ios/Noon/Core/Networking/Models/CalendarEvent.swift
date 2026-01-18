//
//  CalendarEvent.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct CalendarEvent: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let title: String?
    let description: String?
    let start: EventDateTime?
    let end: EventDateTime?
    var isAllDay: Bool {
        start?.isAllDay ?? false
    }
    let attendees: [Attendee]
    let createdBy: Person?
    let calendarId: String?
    let calendarColor: String?
    let location: String?
    let conference: ConferenceInfo?

    enum CodingKeys: String, CodingKey {
        case id
        case summary
        case description
        case start
        case end
        case attendees
        case creator
        case organizer
        case calendarId = "calendar_id"
        case calendarColor = "calendar_color"
        case location
        case conferenceData = "conference_data"
        case hangoutLink = "hangout_link"
    }

    init(id: String,
         title: String? = nil,
         description: String? = nil,
         start: EventDateTime? = nil,
         end: EventDateTime? = nil,
         attendees: [Attendee] = [],
         createdBy: Person? = nil,
         calendarId: String? = nil,
         calendarColor: String? = nil,
         location: String? = nil,
         conference: ConferenceInfo? = nil) {
        self.id = id
        self.title = title
        self.description = description
        self.start = start
        self.end = end
        self.attendees = attendees
        self.createdBy = createdBy
        self.calendarId = calendarId
        self.calendarColor = calendarColor
        self.location = location
        self.conference = conference
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try container.decode(String.self, forKey: .id)
        self.title = try container.decodeIfPresent(String.self, forKey: .summary)
        self.description = try container.decodeIfPresent(String.self, forKey: .description)
        self.start = try container.decodeIfPresent(EventDateTime.self, forKey: .start)
        self.end = try container.decodeIfPresent(EventDateTime.self, forKey: .end)
        self.attendees = try container.decodeIfPresent([Attendee].self, forKey: .attendees) ?? []

        let creator = try container.decodeIfPresent(Person.self, forKey: .creator)
        let organizer = try container.decodeIfPresent(Person.self, forKey: .organizer)
        self.createdBy = creator ?? organizer

        self.calendarId = try container.decodeIfPresent(String.self, forKey: .calendarId)
        self.calendarColor = try container.decodeIfPresent(String.self, forKey: .calendarColor)
        self.location = try container.decodeIfPresent(String.self, forKey: .location)

        let hangoutLink = CalendarEvent.decodeURL(from: container, forKey: .hangoutLink)
        let rawConference = try container.decodeIfPresent(RawConferenceData.self, forKey: .conferenceData)
        self.conference = ConferenceInfo(rawData: rawConference, hangoutLink: hangoutLink)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encodeIfPresent(title, forKey: .summary)
        try container.encodeIfPresent(description, forKey: .description)
        try container.encodeIfPresent(start, forKey: .start)
        try container.encodeIfPresent(end, forKey: .end)

        if !attendees.isEmpty {
            try container.encode(attendees, forKey: .attendees)
        }

        if let createdBy {
            try container.encode(createdBy, forKey: .creator)
        }

        try container.encodeIfPresent(calendarId, forKey: .calendarId)
        try container.encodeIfPresent(calendarColor, forKey: .calendarColor)
        try container.encodeIfPresent(location, forKey: .location)

        if let conference {
            try container.encodeIfPresent(conference.hangoutLink, forKey: .hangoutLink)
            try container.encode(RawConferenceData(from: conference), forKey: .conferenceData)
        }
    }

    private static func decodeURL<Key: CodingKey>(from container: KeyedDecodingContainer<Key>, forKey key: Key) -> URL? {
        if let direct = try? container.decodeIfPresent(URL.self, forKey: key) {
            return direct
        }
        if let stringValue = try? container.decode(String.self, forKey: key),
           let url = URL(string: stringValue) {
            return url
        }
        return nil
    }
}

extension CalendarEvent {
    struct EventDateTime: Codable, Hashable, Sendable {
        let dateTime: Date?
        let date: String?
        let timeZone: String?

        var isAllDay: Bool {
            date != nil && dateTime == nil
        }

        enum CodingKeys: String, CodingKey {
            case dateTime
            case date
            case timeZone
        }

        private static let fractionalFormatter: ISO8601DateFormatter = {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [
                .withInternetDateTime,
                .withFractionalSeconds
            ]
            return formatter
        }()

        private static let fallbackFormatter: ISO8601DateFormatter = {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime]
            return formatter
        }()

        init(dateTime: Date? = nil, date: String? = nil, timeZone: String? = nil) {
            self.dateTime = dateTime
            self.date = date
            self.timeZone = timeZone
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            self.timeZone = try container.decodeIfPresent(String.self, forKey: .timeZone)

            if let dateTimeString = try container.decodeIfPresent(String.self, forKey: .dateTime) {
                if let parsed = EventDateTime.fractionalFormatter.date(from: dateTimeString) {
                    self.dateTime = parsed
                } else {
                    self.dateTime = EventDateTime.fallbackFormatter.date(from: dateTimeString)
                }
            } else {
                self.dateTime = nil
            }

            self.date = try container.decodeIfPresent(String.self, forKey: .date)
        }

        func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            if let dateTime {
                let formatted = EventDateTime.fractionalFormatter.string(from: dateTime)
                try container.encode(formatted, forKey: .dateTime)
            }
            if let date {
                try container.encode(date, forKey: .date)
            }
            if let timeZone {
                try container.encode(timeZone, forKey: .timeZone)
            }
        }
    }

    struct Person: Codable, Hashable, Sendable {
        let email: String?
        let displayName: String?
    }

    struct Attendee: Codable, Hashable, Sendable {
        let email: String?
        let displayName: String?
        let responseStatus: String?
    }

    struct ConferenceInfo: Codable, Hashable, Sendable {
        let hangoutLink: URL?
        let conferenceId: String?
        let entryPoints: [EntryPoint]
        let notes: String?

        struct EntryPoint: Codable, Hashable, Sendable {
            let type: String?
            let uri: URL?
            let label: String?
            let pin: String?
        }

        init(hangoutLink: URL?, conferenceId: String?, entryPoints: [EntryPoint], notes: String?) {
            self.hangoutLink = hangoutLink
            self.conferenceId = conferenceId
            self.entryPoints = entryPoints
            self.notes = notes
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            self.hangoutLink = try container.decodeIfPresent(URL.self, forKey: .hangoutLink)
            self.conferenceId = try container.decodeIfPresent(String.self, forKey: .conferenceId)
            self.entryPoints = try container.decodeIfPresent([EntryPoint].self, forKey: .entryPoints) ?? []
            self.notes = try container.decodeIfPresent(String.self, forKey: .notes)
        }

        func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encodeIfPresent(hangoutLink, forKey: .hangoutLink)
            try container.encodeIfPresent(conferenceId, forKey: .conferenceId)
            if !entryPoints.isEmpty {
                try container.encode(entryPoints, forKey: .entryPoints)
            }
            try container.encodeIfPresent(notes, forKey: .notes)
        }

        private enum CodingKeys: String, CodingKey {
            case hangoutLink
            case conferenceId
            case entryPoints
            case notes
        }
    }

    fileprivate struct RawConferenceData: Codable {
        let conferenceId: String?
        let entryPoints: [ConferenceInfo.EntryPoint]?
        let notes: String?
    }
}

private extension CalendarEvent.ConferenceInfo {
    init?(rawData: CalendarEvent.RawConferenceData?, hangoutLink: URL?) {
        guard rawData != nil || hangoutLink != nil else {
            return nil
        }
        self.init(
            hangoutLink: hangoutLink,
            conferenceId: rawData?.conferenceId,
            entryPoints: rawData?.entryPoints ?? [],
            notes: rawData?.notes
        )
    }
}

private extension CalendarEvent.RawConferenceData {
    init(from conference: CalendarEvent.ConferenceInfo) {
        self.init(
            conferenceId: conference.conferenceId,
            entryPoints: conference.entryPoints.isEmpty ? nil : conference.entryPoints,
            notes: conference.notes
        )
    }
}

struct DisplayEvent: Identifiable, Hashable, Sendable {
    enum Style: Hashable, Sendable {
        case highlight
        case update
        case destructive
        case new
    }
    
    let event: CalendarEvent
    let style: Style?
    var isHidden: Bool
    
    var id: String { event.id }
    
    init(event: CalendarEvent, style: Style? = nil, isHidden: Bool = false) {
        self.event = event
        self.style = style
        self.isHidden = isHidden
    }
    
    // Custom Hashable conformance - isHidden doesn't affect equality/hashing
    func hash(into hasher: inout Hasher) {
        hasher.combine(event)
        hasher.combine(style)
    }
    
    static func == (lhs: DisplayEvent, rhs: DisplayEvent) -> Bool {
        lhs.event == rhs.event && lhs.style == rhs.style
    }
}

