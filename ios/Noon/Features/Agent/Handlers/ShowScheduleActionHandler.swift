//
//  ShowScheduleActionHandler.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct ScheduleDisplayConfiguration {
    let date: Date
}

protocol ShowScheduleActionHandling {
    func configuration(for response: AgentResponse) -> ScheduleDisplayConfiguration
}

struct ShowScheduleActionHandler: ShowScheduleActionHandling {
    private let calendar: Calendar

    init(
        calendar: Calendar = .autoupdatingCurrent
    ) {
        self.calendar = calendar
    }

    func configuration(for response: AgentResponse) -> ScheduleDisplayConfiguration {
        switch response {
        case .showSchedule(let showSchedule):
            // Use default ISO8601DateFormatter which handles timezone offsets automatically
            let formatter = ISO8601DateFormatter()
            guard let start = formatter.date(from: showSchedule.metadata.start_date) else {
                print("ERROR: Failed to parse start_date from show-schedule response: \(showSchedule.metadata.start_date)")
                fatalError("Cannot parse start_date from show-schedule response: \(showSchedule.metadata.start_date)")
            }
            
            // The date string already represents a specific point in time with a timezone.
            // We want to show the schedule for the calendar day that this date falls on
            // in the calendar's timezone, so we use startOfDay to normalize it.
            let derived = calendar.startOfDay(for: start)
            return ScheduleDisplayConfiguration(date: derived)
        default:
            return ScheduleDisplayConfiguration(date: calendar.startOfDay(for: Date()))
        }
    }
}

