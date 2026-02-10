//
//  ScheduleScrollTarget.swift
//  Noon
//
//  Target for programmatic scrolling in SwipeableScheduleView.
//

import Foundation

struct ScheduleScrollTarget: Equatable {
    let date: Date
    /// Fractional hour (0–24), nil = day only
    let timeOfDay: Double?
}
