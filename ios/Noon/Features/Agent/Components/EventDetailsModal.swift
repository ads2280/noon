//
//  EventDetailsModal.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

struct EventDetailsModal: View {
    let event: CalendarEvent
    
    private let cornerRadius: CGFloat = 22
    private let horizontalPadding: CGFloat = 24 // Match AgentModal horizontal padding
    private let verticalPadding: CGFloat = 20
    
    var body: some View {
        HStack(spacing: 0) {
            Spacer()
                .frame(width: horizontalPadding)
            
            ZStack {
                // Content layer
                VStack(alignment: .leading, spacing: 0) {
                    // Header with title
                    HStack(alignment: .top) {
                        Text(event.title ?? "Untitled Event")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(ColorPalette.Text.primary)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.horizontal, horizontalPadding)
                    .padding(.top, 16)
                    .padding(.bottom, 12)
                    
                    // Only show divider if there's content below
                    if hasAnyDetails() {
                        Divider()
                            .background(ColorPalette.Surface.overlay)
                            .padding(.horizontal, horizontalPadding)
                    }
                    
                    VStack(alignment: .leading, spacing: 12) {
                        // Date/Time section
                        if let dateTimeInfo = formatDateTime() {
                            detailRow(
                                icon: "calendar",
                                title: dateTimeInfo
                            )
                        }
                        
                        // Location section
                        if let location = event.location, !location.isEmpty {
                            detailRow(
                                icon: "mappin.circle.fill",
                                title: location
                            )
                        }
                        
                        // Description section
                        if let description = event.description, !description.isEmpty {
                            detailRow(
                                icon: "text.alignleft",
                                title: description,
                                isMultiline: true
                            )
                        }
                        
                        // Attendees section
                        if !event.attendees.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                HStack(spacing: 8) {
                                    Image(systemName: "person.2.fill")
                                        .font(.system(size: 14))
                                        .foregroundStyle(ColorPalette.Text.secondary)
                                        .frame(width: 18)
                                    
                                    Text("Attendees")
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundColor(ColorPalette.Text.secondary)
                                }
                                
                                ForEach(Array(event.attendees.enumerated()), id: \.offset) { _, attendee in
                                    attendeeRow(attendee: attendee)
                                        .padding(.leading, 26)
                                }
                            }
                        }
                        
                        // Conference/Meeting link section
                        if let conference = event.conference {
                            if let hangoutLink = conference.hangoutLink {
                                detailRow(
                                    icon: "video.fill",
                                    title: "Join Meeting",
                                    action: {
                                        UIApplication.shared.open(hangoutLink)
                                    }
                                )
                            } else if !conference.entryPoints.isEmpty {
                                if let firstEntryPoint = conference.entryPoints.first,
                                   let uri = firstEntryPoint.uri {
                                    detailRow(
                                        icon: "video.fill",
                                        title: firstEntryPoint.label ?? "Join Meeting",
                                        action: {
                                            UIApplication.shared.open(uri)
                                        }
                                    )
                                }
                            }
                        }
                    }
                    .padding(.horizontal, horizontalPadding)
                    .padding(.vertical, 12)
                }
            }
            .frame(maxWidth: .infinity)
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: cornerRadius))
            .shadow(
                color: Color.black.opacity(0.1),
                radius: 12,
                x: 0,
                y: 4
            )
            
            Spacer()
                .frame(width: horizontalPadding)
        }
        .transition(.opacity.combined(with: .move(edge: .top)))
    }
    
    @ViewBuilder
    private func detailRow(
        icon: String,
        title: String,
        isMultiline: Bool = false,
        action: (() -> Void)? = nil
    ) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(ColorPalette.Text.secondary)
                .frame(width: 18)
            
            if let action = action {
                Button {
                    action()
                } label: {
                    Text(title)
                        .font(.system(size: 13, weight: .regular))
                        .foregroundColor(ColorPalette.Semantic.primary)
                        .lineLimit(isMultiline ? 3 : 2)
                        .multilineTextAlignment(.leading)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                Text(title)
                    .font(.system(size: 13, weight: .regular))
                    .foregroundColor(ColorPalette.Text.primary)
                    .lineLimit(isMultiline ? 3 : 2)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
    
    @ViewBuilder
    private func attendeeRow(attendee: CalendarEvent.Attendee) -> some View {
        HStack(spacing: 6) {
            Text(attendee.displayName ?? attendee.email ?? "Unknown")
                .font(.system(size: 13, weight: .regular))
                .foregroundColor(ColorPalette.Text.primary)
            
            if let responseStatus = attendee.responseStatus {
                statusIcon(for: responseStatus)
            }
        }
    }
    
    @ViewBuilder
    private func statusIcon(for status: String) -> some View {
        let (iconName, color) = statusIconInfo(for: status)
        Image(systemName: iconName)
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(color)
            .frame(width: 16, height: 16)
    }
    
    private func statusIconInfo(for status: String) -> (iconName: String, color: Color) {
        switch status.lowercased() {
        case "accepted":
            return ("checkmark.circle.fill", ColorPalette.Semantic.success)
        case "declined":
            return ("xmark.circle.fill", ColorPalette.Semantic.destructive)
        case "tentative":
            return ("clock.fill", ColorPalette.Semantic.warning)
        case "needsaction":
            return ("clock", ColorPalette.Text.secondary)
        default:
            return ("circle", ColorPalette.Text.secondary)
        }
    }
    
    private func hasAnyDetails() -> Bool {
        formatDateTime() != nil ||
        (event.location != nil && !event.location!.isEmpty) ||
        (event.description != nil && !event.description!.isEmpty) ||
        !event.attendees.isEmpty ||
        event.conference != nil
    }
    
    private func formatDateTime() -> String? {
        guard let start = event.start else { return nil }
        
        let calendar = Calendar.autoupdatingCurrent
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale.autoupdatingCurrent
        
        if event.isAllDay {
            // All-day event: format as date only
            if let dateString = start.date {
                let isoFormatter = DateFormatter()
                isoFormatter.dateFormat = "yyyy-MM-dd"
                isoFormatter.timeZone = TimeZone(secondsFromGMT: 0)
                
                if let date = isoFormatter.date(from: dateString) {
                    dateFormatter.dateStyle = .medium
                    dateFormatter.timeStyle = .none
                    return dateFormatter.string(from: date)
                }
            }
        } else {
            // Timed event: format as date and time range
            guard let startDateTime = start.dateTime,
                  let end = event.end,
                  let endDateTime = end.dateTime else {
                return nil
            }
            
            dateFormatter.dateStyle = .medium
            dateFormatter.timeStyle = .short
            
            let startFormatted = dateFormatter.string(from: startDateTime)
            
            // Check if end is on the same day
            if calendar.isDate(startDateTime, inSameDayAs: endDateTime) {
                // Same day: "Date, Start Time – End Time"
                let timeFormatter = DateFormatter()
                timeFormatter.locale = Locale.autoupdatingCurrent
                timeFormatter.dateStyle = .none
                timeFormatter.timeStyle = .short
                let endTimeFormatted = timeFormatter.string(from: endDateTime)
                return "\(startFormatted) – \(endTimeFormatted)"
            } else {
                // Different days: "Start Date, Time – End Date, Time"
                let endFormatted = dateFormatter.string(from: endDateTime)
                return "\(startFormatted) – \(endFormatted)"
            }
        }
        
        return nil
    }
    
}

#Preview {
    ZStack {
        ColorPalette.Gradients.backgroundBase
            .ignoresSafeArea()
        
        VStack {
            Spacer()
            
            EventDetailsModal(
                event: CalendarEvent(
                    id: "1",
                    title: "Team Meeting",
                    description: "Weekly team sync to discuss progress and blockers",
                    start: CalendarEvent.EventDateTime(
                        dateTime: Date().addingTimeInterval(3600),
                        date: nil,
                        timeZone: TimeZone.autoupdatingCurrent.identifier
                    ),
                    end: CalendarEvent.EventDateTime(
                        dateTime: Date().addingTimeInterval(7200),
                        date: nil,
                        timeZone: TimeZone.autoupdatingCurrent.identifier
                    ),
                    attendees: [
                        CalendarEvent.Attendee(
                            email: "john@example.com",
                            displayName: "John Doe",
                            responseStatus: "accepted"
                        ),
                        CalendarEvent.Attendee(
                            email: "jane@example.com",
                            displayName: "Jane Smith",
                            responseStatus: "tentative"
                        )
                    ],
                    location: "Conference Room A",
                    conference: nil
                )
            )
        }
        .padding()
    }
}
