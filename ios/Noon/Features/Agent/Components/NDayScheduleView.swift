//
//  NDayScheduleView.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import SwiftUI

struct NDayScheduleView: View {
    let startDate: Date
    let numberOfDays: Int
    let events: [DisplayEvent]
    let focusEvent: ScheduleFocusEvent?

    private let hours = Array(0..<24)
    @State private var scrollViewProxy: ScrollViewProxy?
    @State private var lastScrolledFocusEventID: String?

    private let calendar = Calendar.autoupdatingCurrent

    init(
        startDate: Date,
        numberOfDays: Int = 2,
        events: [DisplayEvent],
        focusEvent: ScheduleFocusEvent? = nil
    ) {
        self.startDate = calendar.startOfDay(for: startDate)
        self.numberOfDays = max(1, numberOfDays)
        self.events = events
        self.focusEvent = focusEvent
    }

    var body: some View {
        GeometryReader { geometry in
            let totalEventWidth = geometry.size.width * (2.0 / 3.0)
            let gridLeading = (geometry.size.width - totalEventWidth) / 2.0
            let dayColumnWidth = totalEventWidth / CGFloat(numberOfDays)
            let labelSpacing: CGFloat = 12
            let labelWidth = max(gridLeading - labelSpacing, 0)
            let hourHeight: CGFloat = 40
            let timelineTopInset: CGFloat = 6
            let gridHeight = timelineTopInset + hourHeight * CGFloat(hours.count)
            let lineColor = ColorPalette.Surface.overlay.opacity(1)
            let scheduleBottomInset: CGFloat = 12

            let dates = (0..<numberOfDays).compactMap { offset in
                calendar.date(byAdding: .day, value: offset, to: startDate)
            }
            let columnLeadings = (0..<numberOfDays).map { index in
                gridLeading + dayColumnWidth * CGFloat(index)
            }

            VStack(alignment: .leading, spacing: 12) {
                dateHeaders(dates: dates, columnLeadings: columnLeadings, dayColumnWidth: dayColumnWidth, gridLeading: gridLeading)

                scheduleScrollView(
                    totalEventWidth: totalEventWidth,
                    gridLeading: gridLeading,
                    dayColumnWidth: dayColumnWidth,
                    columnLeadings: columnLeadings,
                    dates: dates,
                    gridHeight: gridHeight,
                    lineColor: lineColor,
                    timelineTopInset: timelineTopInset,
                    hourHeight: hourHeight,
                    labelWidth: labelWidth,
                    labelSpacing: labelSpacing
                )
                .padding(.bottom, scheduleBottomInset)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
        .padding(.top, 4)
        .padding(.bottom, 12)
    }

    @ViewBuilder
    private func dateHeaders(
        dates: [Date],
        columnLeadings: [CGFloat],
        dayColumnWidth: CGFloat,
        gridLeading: CGFloat
    ) -> some View {
        // When n=1, match ScheduleView exactly
        if numberOfDays == 1, let date = dates.first {
            Text(Self.dateFormatter.string(from: date))
                .font(.footnote.weight(.semibold))
                .foregroundStyle(ColorPalette.Text.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.leading, gridLeading)
                .accessibilityIdentifier("schedule-date-label")
        } else {
            HStack(spacing: 0) {
                ForEach(Array(dates.enumerated()), id: \.element) { index, date in
                    Text(Self.dateFormatter.string(from: date))
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(ColorPalette.Text.secondary)
                        .frame(width: dayColumnWidth, alignment: .leading)
                        .padding(.leading, index == 0 ? columnLeadings[0] : 0)
                }
            }
            .accessibilityIdentifier("schedule-date-headers")
        }
    }

    @ViewBuilder
    private func scheduleScrollView(
        totalEventWidth: CGFloat,
        gridLeading: CGFloat,
        dayColumnWidth: CGFloat,
        columnLeadings: [CGFloat],
        dates: [Date],
        gridHeight: CGFloat,
        lineColor: Color,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat,
        labelWidth: CGFloat,
        labelSpacing: CGFloat
    ) -> some View {
        let cornerRadius: CGFloat = 8

        let content = ZStack(alignment: .topLeading) {
            Canvas { context, _ in
                for index in 0...hours.count {
                    let y = timelineTopInset + hourHeight * CGFloat(index)
                    var path = Path()
                    path.move(to: CGPoint(x: gridLeading, y: y))
                    path.addLine(to: CGPoint(x: gridLeading + totalEventWidth, y: y))
                    context.stroke(path, with: .color(lineColor), lineWidth: 1)
                }
            }
            .frame(width: totalEventWidth + gridLeading * 2, height: gridHeight)

            Color.clear
                .frame(width: totalEventWidth, height: gridHeight)
                .position(
                    x: gridLeading + totalEventWidth / 2,
                    y: gridHeight / 2
                )

            if labelWidth > 0 {
                ForEach(hours, id: \.self) { hour in
                    Text(hourLabel(for: hour))
                        .font(.caption.weight(.medium))
                        .foregroundStyle(ColorPalette.Text.secondary.opacity(0.9))
                        .frame(width: labelWidth, alignment: .trailing)
                        .position(
                            x: gridLeading - labelSpacing - (labelWidth / 2),
                            y: timelineTopInset + hourHeight * CGFloat(hour)
                        )
                }
            }

            // Add invisible scroll anchors at regular intervals (every 15 minutes)
            ForEach(0..<(24 * 4), id: \.self) { index in
                let hourFraction = Double(index) / 4.0
                let yPosition = timelineTopInset + hourHeight * CGFloat(hourFraction)
                Color.clear
                    .frame(width: 1, height: 1)
                    .position(x: gridLeading + totalEventWidth / 2, y: yPosition)
                    .id("hour-\(hourFraction)")
            }
            
            // Render events for each day column
            ForEach(Array(dates.enumerated()), id: \.element) { dayIndex, day in
                let dayEvents = eventsForDay(events, day: day)
                let columnLeading = columnLeadings[dayIndex]
                
                // When n=1, use totalEventWidth (which equals gridWidth) to match ScheduleView exactly
                let eventWidth = numberOfDays == 1 ? totalEventWidth : dayColumnWidth
                let centerX = numberOfDays == 1 ? gridLeading + totalEventWidth / 2 : columnLeading + dayColumnWidth / 2
                
                ForEach(dayEvents) { event in
                    if let layout = layoutInfo(for: event, day: day, focusEvent: focusEvent) {
                        let eventHeight = hourHeight * CGFloat(layout.durationHours)
                        let topPosition = timelineTopInset + hourHeight * CGFloat(layout.startHour)
                        let centerY = topPosition + eventHeight / 2

                        ScheduleEventCard(
                            title: layout.title,
                            timeRange: layout.timeRange,
                            showTimeRange: layout.shouldShowTimeRange,
                            cornerRadius: cornerRadius,
                            style: layout.style
                        )
                        .frame(width: eventWidth, height: eventHeight, alignment: .top)
                        .position(x: centerX, y: centerY)
                    }
                }
            }
        }
        .frame(width: totalEventWidth + gridLeading * 2, height: gridHeight, alignment: .topLeading)
        .clipped()

        ScrollViewReader { proxy in
            if #available(iOS 17.0, *) {
                ScrollView(.vertical, showsIndicators: false) {
                    content
                }
                .scrollBounceBehavior(.basedOnSize)
                .clipped()
                .onAppear {
                    scrollViewProxy = proxy
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        dates: dates,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                        hourHeight: hourHeight
                    )
                }
                .onChange(of: focusEvent?.eventID) {
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        dates: dates,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                        hourHeight: hourHeight
                    )
                }
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    content
                }
                .clipped()
                .onAppear {
                    scrollViewProxy = proxy
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        dates: dates,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                        hourHeight: hourHeight
                    )
                }
                .onChange(of: focusEvent?.eventID) {
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        dates: dates,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                        hourHeight: hourHeight
                    )
                }
            }
        }
    }

    private func hourLabel(for hour: Int) -> String {
        switch hour {
        case 0:
            return "12 AM"
        case 1..<12:
            return "\(hour) AM"
        case 12:
            return "12 PM"
        case 13..<24:
            return "\(hour - 12) PM"
        default:
            return "12 AM"
        }
    }
    
    private func scrollToFocusEventIfNeeded(
        proxy: ScrollViewProxy,
        dates: [Date],
        gridHeight: CGFloat,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat
    ) {
        guard let focusEvent else {
            lastScrolledFocusEventID = nil
            return
        }
        
        // Avoid scrolling multiple times for the same event
        if lastScrolledFocusEventID == focusEvent.eventID {
            return
        }
        
        guard let targetEvent = events.first(where: { $0.id == focusEvent.eventID }),
              let targetDay = dates.first(where: { day in
                  guard let startDate = targetEvent.event.start?.dateTime else { return false }
                  return calendar.isDate(startDate, inSameDayAs: day)
              }),
              let layout = layoutInfo(for: targetEvent, day: targetDay, focusEvent: focusEvent) else {
            return
        }
        
        let eventStartHour = layout.startHour
        
        // Scroll to position the event's start time at 1/3 from the top
        scrollToTime(
            hour: eventStartHour,
            proxy: proxy,
            gridHeight: gridHeight,
            timelineTopInset: timelineTopInset,
            hourHeight: hourHeight
        )
        
        lastScrolledFocusEventID = focusEvent.eventID
    }
    
    private func scrollToTime(
        hour: Double,
        proxy: ScrollViewProxy,
        gridHeight: CGFloat,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat
    ) {
        // Find the nearest anchor point (every 15 minutes = 0.25 hours)
        let roundedHour = (hour * 4).rounded() / 4.0
        let anchorID = "hour-\(roundedHour)"
        
        // Scroll to the anchor with the top of the event at 1/3 from viewport top
        withAnimation(.easeInOut(duration: 0.3)) {
            proxy.scrollTo(anchorID, anchor: UnitPoint(x: 0.5, y: 1.0 / 3.0))
        }
    }

    private func eventsForDay(_ events: [DisplayEvent], day: Date) -> [DisplayEvent] {
        return events.filter { event in
            guard let startDate = event.event.start?.dateTime else { return false }
            return calendar.isDate(startDate, inSameDayAs: day)
        }
    }

    static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.setLocalizedDateFormatFromTemplate("E d")
        return formatter
    }()

    static let timeRangeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.timeStyle = .short
        formatter.dateStyle = .none
        return formatter
    }()
}

private extension NDayScheduleView {
    struct EventLayout {
        let startHour: Double
        let endHour: Double
        let durationHours: Double
        let title: String
        let timeRange: String
        let shouldShowTimeRange: Bool
        let style: ScheduleEventCard.Style
    }

    func layoutInfo(for displayEvent: DisplayEvent, day: Date, focusEvent: ScheduleFocusEvent?) -> EventLayout? {
        let event = displayEvent.event
        guard
            let startDate = event.start?.dateTime,
            let endDate = event.end?.dateTime
        else { return nil }

        guard calendar.isDate(startDate, inSameDayAs: day) else { return nil }

        let startOfDay = calendar.startOfDay(for: day)
        let startComponents = calendar.dateComponents([.minute, .second], from: startOfDay, to: startDate)
        let endComponents = calendar.dateComponents([.minute, .second], from: startOfDay, to: endDate)

        guard
            let startMinutes = startComponents.minute,
            let endMinutes = endComponents.minute
        else { return nil }

        let startSeconds = Double(startComponents.second ?? 0)
        let endSeconds = Double(endComponents.second ?? 0)

        let startHour = (Double(startMinutes) + startSeconds / 60) / 60
        let endHour = (Double(endMinutes) + endSeconds / 60) / 60
        let duration = endHour - startHour

        guard duration > 0 else { return nil }

        let timeRange: String
        if let start = event.start?.dateTime, let end = event.end?.dateTime {
            let formattedStart = Self.timeRangeFormatter.string(from: start)
            let formattedEnd = Self.timeRangeFormatter.string(from: end)
            timeRange = "\(formattedStart) – \(formattedEnd)"
        } else {
            timeRange = ""
        }

        let title = event.title?.isEmpty == false ? event.title! : "Untitled Event"
        let shouldShowTimeRange = duration >= 1.0

        let style: ScheduleEventCard.Style
        if let focusEvent, focusEvent.eventID == displayEvent.id {
            style = cardStyle(for: focusEvent.style)
        } else {
            style = cardStyle(for: displayEvent.style)
        }

        return EventLayout(
            startHour: startHour,
            endHour: endHour,
            durationHours: duration,
            title: title,
            timeRange: timeRange,
            shouldShowTimeRange: shouldShowTimeRange,
            style: style
        )
    }

    func cardStyle(for style: DisplayEvent.Style?) -> ScheduleEventCard.Style {
        guard let style else { return .standard }
        return cardStyle(for: style)
    }

    private func cardStyle(for style: DisplayEvent.Style) -> ScheduleEventCard.Style {
        switch style {
        case .highlight:
            return .highlight
        case .update:
            return .update
        case .destructive:
            return .destructive
        }
    }
}
