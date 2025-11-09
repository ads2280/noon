//
//  ScheduleView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct ScheduleView: View {
    let date: Date
    let events: [DisplayEvent]

    private let hours = Array(0..<24)

    init(date: Date, events: [DisplayEvent]) {
        self.date = date
        self.events = events
    }

    var body: some View {
        GeometryReader { geometry in
            let gridWidth = geometry.size.width * (2.0 / 3.0)
            let gridLeading = (geometry.size.width - gridWidth) / 2.0
            let labelSpacing: CGFloat = 12
            let labelWidth = max(gridLeading - labelSpacing, 0)
            let hourHeight: CGFloat = 40
            let timelineTopInset: CGFloat = 6
            let gridHeight = timelineTopInset + hourHeight * CGFloat(hours.count)
            let lineColor = ColorPalette.Surface.overlay.opacity(1)
            let scheduleBottomInset: CGFloat = 12

            VStack(alignment: .leading, spacing: 12) {
                Text(formattedDate)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(ColorPalette.Text.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, gridLeading)
                    .accessibilityIdentifier("schedule-date-label")

                scheduleScrollView(
                    gridWidth: gridWidth,
                    gridLeading: gridLeading,
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
    private func scheduleScrollView(
        gridWidth: CGFloat,
        gridLeading: CGFloat,
        gridHeight: CGFloat,
        lineColor: Color,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat,
        labelWidth: CGFloat,
        labelSpacing: CGFloat
    ) -> some View {
        let eventHorizontalInset: CGFloat = 12
        let cornerRadius: CGFloat = 12

        let content = ZStack(alignment: .topLeading) {
            Canvas { context, _ in
                for index in 0...hours.count {
                    let y = timelineTopInset + hourHeight * CGFloat(index)
                    var path = Path()
                    path.move(to: CGPoint(x: gridLeading, y: y))
                    path.addLine(to: CGPoint(x: gridLeading + gridWidth, y: y))
                    context.stroke(path, with: .color(lineColor), lineWidth: 1)
                }
            }
            .frame(width: gridWidth + gridLeading * 2, height: gridHeight)

            Color.clear
                .frame(width: gridWidth, height: gridHeight)
                .position(
                    x: gridLeading + gridWidth / 2,
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

            ForEach(events) { event in
                if let layout = layoutInfo(for: event) {
                    let eventHeight = hourHeight * CGFloat(layout.durationHours)
                    let topPosition = timelineTopInset + hourHeight * CGFloat(layout.startHour)
                    let centerY = topPosition + eventHeight / 2
                    let eventWidth = max(gridWidth - eventHorizontalInset * 2, 0)
                    let centerX = gridLeading + gridWidth / 2

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
        .frame(width: gridWidth + gridLeading * 2, height: gridHeight, alignment: .topLeading)
        .clipped()

        if #available(iOS 17.0, *) {
            ScrollView(.vertical, showsIndicators: false) {
                content
            }
            .scrollBounceBehavior(.basedOnSize)
            .clipped()
        } else {
            ScrollView(.vertical, showsIndicators: false) {
                content
            }
            .clipped()
        }
    }

    private var formattedDate: String {
        Self.dateFormatter.string(from: date)
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
}

private extension ScheduleView {
    struct EventLayout {
        let event: DisplayEvent
        let startHour: Double
        let endHour: Double
        let durationHours: Double
        let title: String
        let timeRange: String
        let shouldShowTimeRange: Bool
        let style: ScheduleEventCard.Style
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

    func layoutInfo(for displayEvent: DisplayEvent) -> EventLayout? {
        let event = displayEvent.event
        guard
            let startDate = event.start?.dateTime,
            let endDate = event.end?.dateTime
        else { return nil }

        let calendar = Calendar.autoupdatingCurrent

        guard calendar.isDate(startDate, inSameDayAs: date) else { return nil }

        let startOfDay = calendar.startOfDay(for: date)
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
        switch displayEvent.style {
        case .some(.highlight):
            style = .highlight
        case .some(.update):
            style = .update
        case .some(.destructive):
            style = .destructive
        case .none:
            style = .standard
        }

        return EventLayout(
            event: displayEvent,
            startHour: startHour,
            endHour: endHour,
            durationHours: duration,
            title: title,
            timeRange: timeRange,
            shouldShowTimeRange: shouldShowTimeRange,
            style: style
        )
    }
}

#Preview {
    ScheduleView(
        date: Date(),
        events: ScheduleDisplayHelper.getDisplayEvents(
            for: Date(),
            highlightEventID: "mock-event-lunch",
            destructiveEventID: "mock-event-product-review"
        )
    )
    .padding()
    .frame(height: 600)
    .background(Color.black.opacity(0.9))
}

