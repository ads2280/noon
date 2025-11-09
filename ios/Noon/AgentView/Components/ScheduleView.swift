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
    private let mockEvents = MockEvent.sampleEvents

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

            ForEach(mockEvents) { event in
                let eventHeight = hourHeight * CGFloat(event.durationHours)
                let topPosition = timelineTopInset + hourHeight * CGFloat(event.startHour)
                let centerY = topPosition + eventHeight / 2
                let eventWidth = max(gridWidth - eventHorizontalInset * 2, 0)
                let centerX = gridLeading + gridWidth / 2
                let shouldShowTimeRange = event.durationHours >= 1

                ScheduleEventCard(
                    title: event.title,
                    timeRange: event.timeRange,
                    showTimeRange: shouldShowTimeRange,
                    cornerRadius: cornerRadius,
                    style: event.style
                )
                .frame(width: eventWidth, height: eventHeight, alignment: .top)
                .position(x: centerX, y: centerY)
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
    struct MockEvent: Identifiable {
        let id = UUID()
        let title: String
        let timeRange: String
        let startHour: Double
        let endHour: Double
        let style: ScheduleEventCard.Style

        var durationHours: Double {
            max(endHour - startHour, 0.25)
        }

        static let sampleEvents: [MockEvent] = [
            MockEvent(
                title: "Daily Standup",
                timeRange: "9:00 – 9:30 AM",
                startHour: 9.0,
                endHour: 9.5,
                style: .standard
            ),
            MockEvent(
                title: "Product Review",
                timeRange: "11:00 AM – 12:15 PM",
                startHour: 11.0,
                endHour: 12.25,
                style: .standard
            ),
            MockEvent(
                title: "Lunch with Jordan",
                timeRange: "1:00 – 1:45 PM",
                startHour: 13.0,
                endHour: 13.75,
                style: .highlight
            ),
            MockEvent(
                title: "AI Strategy Session",
                timeRange: "3:30 – 4:30 PM",
                startHour: 15.5,
                endHour: 16.5,
                style: .standard
            )
        ]
    }

    static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.setLocalizedDateFormatFromTemplate("E d")
        return formatter
    }()
}

#Preview {
    ScheduleView(date: Date())
        .padding()
        .frame(height: 600)
        .background(Color.black.opacity(0.9))
}

