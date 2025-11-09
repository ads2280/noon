//
//  ScheduleView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct ScheduleView: View {
    let date: Date

    private let hours = Array(0..<24)

    var body: some View {
        GeometryReader { geometry in
            let gridWidth = geometry.size.width * (2.0 / 3.0)
            let gridLeading = (geometry.size.width - gridWidth) / 2.0
            let labelSpacing: CGFloat = 12
            let labelWidth = max(gridLeading - labelSpacing, 0)
            let hourHeight: CGFloat = 45
            let timelineTopInset: CGFloat = 8
            let gridHeight = timelineTopInset + hourHeight * CGFloat(hours.count)
            let lineColor = ColorPalette.Surface.overlay.opacity(1)
            let scheduleBottomInset: CGFloat = 12
            let events = Self.loadEvents(for: date)

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
                    labelSpacing: labelSpacing,
                    events: events
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
        labelSpacing: CGFloat,
        events: [ScheduleEvent]
    ) -> some View {
        let gridSize = CGSize(width: gridWidth + gridLeading * 2, height: gridHeight)
        let eventWidth = max(gridWidth - 24, 0)
        let minEventHeight: CGFloat = 36

        let gridLines = Canvas { context, _ in
            for index in 0...hours.count {
                let y = timelineTopInset + hourHeight * CGFloat(index)
                var path = Path()
                path.move(to: CGPoint(x: gridLeading, y: y))
                path.addLine(to: CGPoint(x: gridLeading + gridWidth, y: y))
                context.stroke(path, with: .color(lineColor), lineWidth: 1)
            }
        }
        .frame(width: gridSize.width, height: gridSize.height)

        let eventsLayer = ZStack(alignment: .topLeading) {
            if eventWidth > 0 {
                ForEach(events) { event in
                    let startMinutes = event.startMinutes / 60.0
                    let durationHours = max(event.durationMinutes / 60.0, 0.25)
                    let startOffset = timelineTopInset + hourHeight * CGFloat(startMinutes)
                    let eventHeight = hourHeight * CGFloat(durationHours)
                    let displayHeight = max(eventHeight, minEventHeight)
                    let showsTime = durationHours >= 1.0 - 0.01

                    RoundedRectangle(cornerRadius: 14)
                        .fill(ColorPalette.Surface.background.opacity(0.95))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .fill(ColorPalette.Text.secondary.opacity(0.18))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(ColorPalette.Text.secondary.opacity(0.35), lineWidth: 1)
                        )
                        .overlay(alignment: .topLeading) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(event.title)
                                    .font(.caption2.weight(.semibold))
                                    .foregroundStyle(ColorPalette.Text.primary)
                                if showsTime {
                                    Text(event.timeRangeLabel)
                                        .font(.caption2.weight(.medium))
                                        .foregroundStyle(ColorPalette.Text.secondary)
                                }
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(width: eventWidth, height: displayHeight, alignment: .topLeading)
                        .position(
                            x: gridLeading + gridWidth / 2,
                            y: startOffset + displayHeight / 2
                        )
                }
            }
        }
        .frame(width: gridSize.width, height: gridSize.height, alignment: .topLeading)

        let labelsOverlay = ZStack(alignment: .topLeading) {
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
        }
        .frame(width: gridSize.width, height: gridSize.height, alignment: .topLeading)

        let scrollContent = ZStack(alignment: .topLeading) {
            gridLines
            eventsLayer
        }
        .overlay(labelsOverlay)
        .frame(width: gridSize.width, height: gridSize.height, alignment: .topLeading)
        .clipped()

        if #available(iOS 17.0, *) {
            ScrollView(.vertical, showsIndicators: false) {
                scrollContent
            }
            .scrollBounceBehavior(.basedOnSize)
            .clipped()
        } else {
            ScrollView(.vertical, showsIndicators: false) {
                scrollContent
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
    struct ScheduleEvent: Identifiable {
        let id = UUID()
        let title: String
        let start: Date
        let end: Date
        let color: Color

        var startMinutes: Double {
            let components = Calendar.current.dateComponents([.hour, .minute], from: start)
            let hours = Double(components.hour ?? 0)
            let minutes = Double(components.minute ?? 0)
            return hours * 60 + minutes
        }

        var durationMinutes: Double {
            max(end.timeIntervalSince(start) / 60, 0)
        }

        var timeRangeLabel: String {
            let formatter = ScheduleView.timeFormatter
            return "\(formatter.string(from: start)) – \(formatter.string(from: end))"
        }
    }

    static func loadEvents(for date: Date) -> [ScheduleEvent] {
        let calendar = Calendar.current

        func makeEvent(
            _ title: String,
            hour: Int,
            minute: Int,
            durationMinutes: Int,
            color: Color
        ) -> ScheduleEvent? {
            guard
                let start = calendar.date(
                    bySettingHour: hour,
                    minute: minute,
                    second: 0,
                    of: date
                ),
                let end = calendar.date(
                    byAdding: .minute,
                    value: max(durationMinutes, 15),
                    to: start
                )
            else {
                return nil
            }

            return ScheduleEvent(
                title: title,
                start: start,
                end: min(end, calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: date)) ?? end),
                color: color
            )
        }

        return [
            makeEvent(
                "Team Standup",
                hour: 9,
                minute: 0,
                durationMinutes: 45,
                color: ColorPalette.Semantic.secondary
            ),
            makeEvent(
                "Product Review",
                hour: 11,
                minute: 30,
                durationMinutes: 60,
                color: ColorPalette.Semantic.primary
            ),
            makeEvent(
                "Focus Block",
                hour: 14,
                minute: 0,
                durationMinutes: 120,
                color: ColorPalette.Semantic.success
            )
        ].compactMap { $0 }
    }

    static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.setLocalizedDateFormatFromTemplate("E d")
        return formatter
    }()

    static let timeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.dateFormat = "h:mm a"
        return formatter
    }()
}

#Preview {
    ScheduleView(date: Date())
        .padding()
        .frame(height: 600)
        .background(Color.black.opacity(0.9))
}

