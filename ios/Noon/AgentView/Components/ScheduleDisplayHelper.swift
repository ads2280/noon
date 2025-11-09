//
//  ScheduleDisplayHelper.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

enum ScheduleDisplayHelper {
    static func getDisplayEvents(
        for date: Date,
        highlightEventID: String? = nil,
        destructiveEventID: String? = nil
    ) -> [DisplayEvent] {
        let events = makeMockEvents(for: date)
        return events.map { event in
            let style: DisplayEvent.Style?
            if event.id == destructiveEventID {
                style = .destructive
            } else if event.id == highlightEventID {
                style = .highlight
            } else if event.id == "mock-event-ai-strategy" {
                style = .update
            } else {
                style = nil
            }
            return DisplayEvent(event: event, style: style)
        }
    }

    private static func makeMockEvents(for date: Date) -> [CalendarEvent] {
        var calendar = Calendar.autoupdatingCurrent
        let timeZone = TimeZone.autoupdatingCurrent
        calendar.timeZone = timeZone
        let timeZoneIdentifier = timeZone.identifier

        func dateForHour(_ hourFraction: Double) -> Date {
            let normalizedHour = max(0, min(23.75, hourFraction))
            let hour = Int(normalizedHour)
            let minutes = Int(round((normalizedHour - Double(hour)) * 60))
            var components = calendar.dateComponents([.year, .month, .day], from: date)
            components.hour = hour
            components.minute = minutes
            components.second = 0
            components.timeZone = timeZone
            return calendar.date(from: components) ?? date
        }

        func makeEvent(id: String, title: String, startHour: Double, endHour: Double) -> CalendarEvent {
            let startDate = dateForHour(startHour)
            let endDate = dateForHour(endHour)
            let start = CalendarEvent.EventDateTime(
                dateTime: startDate,
                date: nil,
                timeZone: timeZoneIdentifier
            )
            let end = CalendarEvent.EventDateTime(
                dateTime: endDate,
                date: nil,
                timeZone: timeZoneIdentifier
            )
            return CalendarEvent(
                id: id,
                title: title,
                start: start,
                end: end
            )
        }

        return [
            makeEvent(
                id: "mock-event-standup",
                title: "Daily Standup",
                startHour: 9.0,
                endHour: 9.5
            ),
            makeEvent(
                id: "mock-event-product-review",
                title: "Product Review",
                startHour: 11.0,
                endHour: 12.25
            ),
            makeEvent(
                id: "mock-event-lunch",
                title: "Lunch with Jordan",
                startHour: 13.0,
                endHour: 13.75
            ),
            makeEvent(
                id: "mock-event-ai-strategy",
                title: "AI Strategy Session",
                startHour: 15.5,
                endHour: 16.5
            )
        ]
    }
}

