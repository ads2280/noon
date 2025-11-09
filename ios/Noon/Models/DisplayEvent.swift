//
//  DisplayEvent.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct DisplayEvent: Identifiable, Sendable {
    enum Style {
        case highlight
        case update
        case destructive
    }

    let event: CalendarEvent
    let style: Style?

    var id: String { event.id }

    init(event: CalendarEvent, style: Style? = nil) {
        self.event = event
        self.style = style
    }
}

