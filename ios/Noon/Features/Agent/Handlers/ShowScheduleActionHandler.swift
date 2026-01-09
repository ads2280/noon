//
//  ShowScheduleActionHandler.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct ScheduleDisplayConfiguration {
    let date: Date
    let focusEvent: ScheduleFocusEvent?
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
            let formatter = ISO8601DateFormatter()
            formatter.timeZone = .autoupdatingCurrent
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            
            let start = formatter.date(from: showSchedule.metadata.startDateISO)
            let derived = start.map { calendar.startOfDay(for: $0) } ?? calendar.startOfDay(for: Date())
            return ScheduleDisplayConfiguration(date: derived, focusEvent: nil)
        default:
            return ScheduleDisplayConfiguration(date: calendar.startOfDay(for: Date()), focusEvent: nil)
        }
    }
}

