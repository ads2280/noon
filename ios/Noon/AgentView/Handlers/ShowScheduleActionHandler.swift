//
//  ShowScheduleActionHandler.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct ShowScheduleActionResult {
    let startDate: Date
    let displayEvents: [DisplayEvent]
}

protocol ShowScheduleActionHandling {
    func fetchTodaySchedule(accessToken: String) async throws -> ShowScheduleActionResult
}

struct ShowScheduleActionHandler: ShowScheduleActionHandling {
    private let scheduleService: GoogleCalendarScheduleServicing
    private let calendar: Calendar

    init(
        scheduleService: GoogleCalendarScheduleServicing = GoogleCalendarScheduleService(),
        calendar: Calendar = .autoupdatingCurrent
    ) {
        self.scheduleService = scheduleService
        self.calendar = calendar
    }

    func fetchTodaySchedule(accessToken: String) async throws -> ShowScheduleActionResult {
        let startDate = calendar.startOfDay(for: Date())
        let endDate = calendar.date(byAdding: .day, value: 1, to: startDate) ?? startDate
        
        let timezone = TimeZone.autoupdatingCurrent
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = timezone
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        let startDateISO = formatter.string(from: startDate)
        let endDateISO = formatter.string(from: endDate)

        let schedule = try await scheduleService.fetchSchedule(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )

        let events = schedule.events.map { DisplayEvent(event: $0) }

        return ShowScheduleActionResult(
            startDate: startDate,
            displayEvents: events
        )
    }
}

