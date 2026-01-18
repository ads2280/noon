//
//  NDayScheduleView.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import SwiftUI
import UIKit
import Foundation

struct NDayScheduleView: View {
    let startDate: Date
    let numberOfDays: Int
    let events: [DisplayEvent]
    let focusEvent: ScheduleFocusEvent?
    let userTimezone: String?
    let modalBottomPadding: CGFloat

    private let hours = Array(0..<24)
    
    // Event spacing
    private let horizontalEventInset: CGFloat = 5
    private let verticalEventInset: CGFloat = 2
    private let minimumEventHeight: CGFloat = 8
    @State private var scrollViewProxy: ScrollViewProxy?
    @State private var lastScrolledFocusEventID: String?
    @State private var hasScrolledToNoon: Bool = false

    private let calendar = Calendar.autoupdatingCurrent
    
    init(
        startDate: Date,
        numberOfDays: Int = 3,
        events: [DisplayEvent],
        focusEvent: ScheduleFocusEvent? = nil,
        userTimezone: String? = nil,
        modalBottomPadding: CGFloat = 0
    ) {
        self.startDate = calendar.startOfDay(for: startDate)
        self.numberOfDays = max(1, numberOfDays)
        self.events = events
        self.focusEvent = focusEvent
        self.userTimezone = userTimezone
        self.modalBottomPadding = modalBottomPadding
    }

    var body: some View {
        GeometryReader { geometry in
            let horizontalPadding: CGFloat = 0
            let timeLabelAreaWidth = Self.calculateTimeLabelWidth()
            let labelSpacing: CGFloat = 12
            let gridLeading = horizontalPadding + timeLabelAreaWidth + labelSpacing
            let totalEventWidth = geometry.size.width - gridLeading - horizontalPadding
            let dayColumnWidth = totalEventWidth / CGFloat(numberOfDays)
            let labelWidth = timeLabelAreaWidth
            let hourHeight: CGFloat = 40
            let timelineTopInset: CGFloat = 6
            let gridHeight = timelineTopInset + hourHeight * CGFloat(hours.count)
            let lineColor = ColorPalette.Surface.overlay.opacity(1)

            let dates = (0..<numberOfDays).compactMap { offset in
                calendar.date(byAdding: .day, value: offset, to: startDate)
            }
            let columnLeadings = (0..<numberOfDays).map { index in
                gridLeading + dayColumnWidth * CGFloat(index)
            }
            
            // Generate segment cards once for all days
            let segmentCards = generateSegmentCards(from: events, dates: dates)

            VStack(alignment: .leading, spacing: 0) {
                // Date headers row with timezone label
                HStack(alignment: .top, spacing: 0) {
                    timezoneLabel(
                        timeLabelAreaWidth: timeLabelAreaWidth,
                        labelSpacing: labelSpacing
                    )
                    dateHeaders(dates: dates, columnLeadings: columnLeadings, dayColumnWidth: dayColumnWidth, gridLeading: gridLeading)
                }
                
                allDayEventsSection(
                    segmentCards: segmentCards,
                    columnLeadings: columnLeadings,
                    dayColumnWidth: dayColumnWidth,
                    gridLeading: gridLeading,
                    totalEventWidth: totalEventWidth,
                    dates: dates,
                    lineColor: lineColor
                )
                .padding(.leading, gridLeading)

                scheduleScrollView(
                    segmentCards: segmentCards,
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
                    labelSpacing: labelSpacing,
                    contentWidth: geometry.size.width,
                    horizontalPadding: horizontalPadding,
                    focusEvent: focusEvent
                )
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .animation(.spring(response: 0.3, dampingFraction: 0.8), value: modalBottomPadding)
        }
        .padding(.top, 4)
        .ignoresSafeArea(edges: .bottom)
    }

    @ViewBuilder
    private func allDayEventsSection(
        segmentCards: [EventSegmentCard],
        columnLeadings: [CGFloat],
        dayColumnWidth: CGFloat,
        gridLeading: CGFloat,
        totalEventWidth: CGFloat,
        dates: [Date],
        lineColor: Color
    ) -> some View {
        let allDaySegments = segmentCards.filter { $0.isAllDay }
        
        if !allDaySegments.isEmpty {
            let rows = packAllDayEventsIntoRows(allDaySegments, dates: dates)
            let eventHeight: CGFloat = 20
            let rowSpacing: CGFloat = verticalEventInset  // 2px spacing between rows
            let rowHeight: CGFloat = eventHeight + rowSpacing  // 22px per row
            // Total height: for N rows, we need (N * eventHeight) + ((N-1) * rowSpacing)
            // Or: (N-1) * rowHeight + eventHeight
            let topPadding: CGFloat = 4
            let bottomPadding: CGFloat = 2
            let totalHeight: CGFloat = rows.isEmpty ? 0 : (CGFloat(rows.count - 1) * rowHeight) + eventHeight + topPadding + bottomPadding
            
            ZStack(alignment: .topLeading) {
                // Border lines at top and bottom (invisible)
                Canvas { context, size in
                    // Top border line
                    var topPath = Path()
                    topPath.move(to: CGPoint(x: 0, y: 0))
                    topPath.addLine(to: CGPoint(x: size.width, y: 0))
                    context.stroke(topPath, with: .color(lineColor), lineWidth: 1)
                    
                    // Bottom border line
                    var bottomPath = Path()
                    bottomPath.move(to: CGPoint(x: 0, y: totalHeight))
                    bottomPath.addLine(to: CGPoint(x: size.width, y: totalHeight))
                    context.stroke(bottomPath, with: .color(lineColor), lineWidth: 1)
                }
                .frame(maxWidth: .infinity)
                .opacity(0)  // Invisible but still takes up space for layout
                
                // Event cards
                ForEach(rows, id: \.rowIndex) { row in
                    ForEach(row.segments, id: \.id) { segment in
                        allDayEventCard(
                            segment: segment,
                            columnLeadings: columnLeadings,
                            dayColumnWidth: dayColumnWidth,
                            gridLeading: gridLeading,
                            totalEventWidth: totalEventWidth,
                            dates: dates,
                            numberOfDays: numberOfDays
                        )
                        .offset(y: topPadding + CGFloat(row.rowIndex) * rowHeight)
                    }
                }
            }
            .frame(height: totalHeight)
        }
    }
    
    private func allDayEventCard(
        segment: EventSegmentCard,
        columnLeadings: [CGFloat],
        dayColumnWidth: CGFloat,
        gridLeading: CGFloat,
        totalEventWidth: CGFloat,
        dates: [Date],
        numberOfDays: Int
    ) -> some View {
        let cardWidth: CGFloat
        let centerX: CGFloat
        let cornerRadius: CGFloat = 5
        
        // ZStack coordinate system starts at 0 (padding is applied to parent)
        // All calculations should be relative to this origin
        if segment.isSpanning {
            // Spanning card: calculate width based on number of days it spans
            let dayIndices = getDayIndices(for: segment, dates: dates)
            if let firstDayIndex = dayIndices.first {
                let spanCount = dayIndices.count
                // Width = (number of days * dayColumnWidth) - horizontalEventInset
                // This matches the pattern: multiples of day width minus one inset
                // Example: 2 days = 2 * dayColumnWidth - 5px
                let spanWidth = CGFloat(spanCount) * dayColumnWidth - horizontalEventInset
                // cardWidth is used for positioning, actual card width is spanWidth
                cardWidth = CGFloat(spanCount) * dayColumnWidth  // Full width including space for inset
                // Position starting at the first day the event appears on
                let columnStart = CGFloat(firstDayIndex) * dayColumnWidth
                centerX = columnStart + spanWidth / 2  // Center the card starting from the first day
            } else {
                // Fallback if no indices found - shouldn't happen but handle gracefully
                cardWidth = totalEventWidth
                centerX = (totalEventWidth - horizontalEventInset) / 2
            }
        } else {
            // Single-day card in appropriate column - match regular event alignment
            // Find which column this day is in
            if let dayIndex = dates.firstIndex(where: { calendar.isDate($0, inSameDayAs: segment.day) }) {
                let dayColWidth = numberOfDays == 1 ? totalEventWidth : dayColumnWidth
                let eventWidth = dayColWidth - horizontalEventInset
                cardWidth = dayColWidth
                // Calculate centerX relative to padded ZStack origin (0)
                let columnStart = CGFloat(dayIndex) * dayColumnWidth
                centerX = columnStart + eventWidth / 2
            } else {
                // Fallback to first column
                let dayColWidth = numberOfDays == 1 ? totalEventWidth : dayColumnWidth
                let eventWidth = dayColWidth - horizontalEventInset
                cardWidth = dayColWidth
                centerX = eventWidth / 2  // Relative to padded ZStack origin (0)
            }
        }
        
        let style: ScheduleEventCard.Style
        if let focusEvent = self.focusEvent, focusEvent.eventID == segment.eventID {
            style = cardStyle(for: focusEvent.style)
        } else {
            style = cardStyle(for: segment.event.style)
        }
        
        let title = segment.event.event.title?.isEmpty == false ? segment.event.event.title! : "Untitled Event"
        
        let calendarColor = segment.event.event.calendarColor.flatMap { Color.fromHex($0) }
        let actualCardWidth = cardWidth - horizontalEventInset
        
        return ScheduleEventCard(
            title: title,
            cornerRadius: cornerRadius,
            style: style,
            calendarColor: calendarColor
        )
        .frame(width: actualCardWidth, height: 20, alignment: .top)
        .offset(x: centerX - actualCardWidth / 2, y: 0)
    }
    
    @ViewBuilder
    private func timezoneLabel(
        timeLabelAreaWidth: CGFloat,
        labelSpacing: CGFloat
    ) -> some View {
        let abbreviation = getTimezoneAbbreviation(from: userTimezone)
        Text(abbreviation)
            .font(.footnote.weight(.semibold))
            .foregroundStyle(ColorPalette.Text.secondary)
            .frame(width: timeLabelAreaWidth, alignment: .trailing)
            .padding(.trailing, labelSpacing)
            .opacity(0)  // Hidden but still takes up space for layout
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
                }
            }
            .accessibilityIdentifier("schedule-date-headers")
        }
    }

    @ViewBuilder
    private func scheduleScrollView(
        segmentCards: [EventSegmentCard],
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
        labelSpacing: CGFloat,
        contentWidth: CGFloat,
        horizontalPadding: CGFloat,
        focusEvent: ScheduleFocusEvent?
    ) -> some View {
        let cornerRadius: CGFloat = 5

        let scheduleContent = ZStack(alignment: .topLeading) {
            Canvas { context, _ in
                for index in 0...hours.count {
                    let y = timelineTopInset + hourHeight * CGFloat(index)
                    var path = Path()
                    path.move(to: CGPoint(x: gridLeading, y: y))
                    path.addLine(to: CGPoint(x: gridLeading + totalEventWidth, y: y))
                    context.stroke(path, with: .color(lineColor), lineWidth: 1)
                }
            }
            .frame(width: contentWidth, height: gridHeight)

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

            
            // Render timed segment cards for each day column
            let timedSegments = segmentCards.filter { !$0.isAllDay }
            ForEach(Array(dates.enumerated()), id: \.element) { dayIndex, day in
                let daySegments = timedSegments.filter { calendar.isDate($0.day, inSameDayAs: day) }
                let columnLeading = columnLeadings[dayIndex]
                
                // When n=1, use totalEventWidth (which equals gridWidth) to match ScheduleView exactly
                let dayColWidth = numberOfDays == 1 ? totalEventWidth : dayColumnWidth
                let eventWidth = dayColWidth - horizontalEventInset
                let centerX = numberOfDays == 1 ? gridLeading + dayColWidth / 2 : columnLeading + eventWidth / 2
                
                ForEach(daySegments) { segment in
                    if let layout = layoutInfo(for: segment, focusEvent: focusEvent) {
                        let eventHeight = max((hourHeight * CGFloat(layout.durationHours)) - verticalEventInset, minimumEventHeight)
                        let topPosition = timelineTopInset + hourHeight * CGFloat(layout.startHour)
                        let centerY = topPosition + eventHeight / 2

                        let calendarColor = segment.event.event.calendarColor.flatMap { Color.fromHex($0) }

                        ScheduleEventCard(
                            title: layout.title,
                            cornerRadius: cornerRadius,
                            style: layout.style,
                            calendarColor: calendarColor
                        )
                        .frame(width: eventWidth, height: eventHeight, alignment: .top)
                        .position(x: centerX, y: centerY)
                    }
                }
            }
        }
        
        // Calculate padding to maintain consistent spacing between schedule bottom and overlay top
        // The spacing should be the same whether it's just microphone or microphone + modal
        // Heights: microphone container = 96, modal = 88
        // Gap between modal and microphone: 8 (from AgentView VStack spacing)
        // We want consistent spacing value between schedule and the topmost overlay element
        // Increased to 60 to ensure content can scroll past overlay without being hidden
        let spaceToMicrophoneTop: CGFloat = 146
        let modalHeight: CGFloat = 88
        let modalMicrophoneGap: CGFloat = 8 // spacing between modal and microphone in AgentView
        
        // Determine if modal is visible by checking if modalBottomPadding exceeds base microphone padding
        let baseMicrophonePadding: CGFloat = 96 + 8 + 24 // from AgentView calculation
        let isModalVisible = modalBottomPadding > baseMicrophonePadding
        
        // Calculate padding: overlay heights + consistent spacing
        // When no modal: microphone + spacing
        // When modal visible: modal + gap + microphone + spacing (spacing is between schedule and modal top)
        let paddingHeight = spaceToMicrophoneTop + (isModalVisible ? (modalHeight + modalMicrophoneGap) : 0)
        let totalContentHeight = gridHeight + paddingHeight
        
        // Create anchors as direct children of VStack using spacers positioned at correct Y offsets
        // This ensures anchors are findable by scrollTo while being at correct absolute positions
        let anchorsVStack = VStack(spacing: 0) {
            // Special anchor at the very top of the scrollable view (Y=0, above padding)
            Color.clear
                .frame(width: 1, height: 1)
                .id("scroll-top")
            
            ForEach(0..<(24 * 4), id: \.self) { index in
                let hourFraction = Double(index) / 4.0
                let yPosition = timelineTopInset + hourHeight * CGFloat(hourFraction)
                // Normalize anchor ID format to match scrollToTimeDiscrete
                let anchorID = String(format: "hour-%.2f", hourFraction)
                
                // Calculate spacing from previous anchor (or from top for first anchor)
                if index == 0 {
                    // First anchor: add spacer to position at yPosition from top
                    Spacer()
                        .frame(height: yPosition)
                    Color.clear
                        .frame(width: 1, height: 1)
                        .id(anchorID)
                } else {
                    // Subsequent anchors: spacing is 15 minutes = hourHeight/4
                    Color.clear
                        .frame(width: 1, height: hourHeight / 4.0)
                        .id(anchorID)
                }
            }
            // Fill remaining space to reach gridHeight
            Spacer()
                .frame(height: gridHeight - (timelineTopInset + hourHeight * 24))
        }
        .frame(width: contentWidth, height: gridHeight, alignment: .topLeading)
        .allowsHitTesting(false)
        
        let content = VStack(spacing: 0) {
            // Use ZStack to layer scheduleContent and anchors
            ZStack(alignment: .topLeading) {
            scheduleContent
                    .frame(width: contentWidth, height: gridHeight, alignment: .topLeading)
                
                anchorsVStack
            }
                .frame(width: contentWidth, height: gridHeight, alignment: .topLeading)
            
            // Dynamic padding for microphone button and modal visibility
            // Always add padding to allow content to scroll past overlay elements
            Color.clear
                .frame(width: contentWidth, height: paddingHeight)
            
            // Special anchor at the very bottom of the scrollable view (at end of total content)
            Color.clear
                .frame(width: 1, height: 1)
                .id("scroll-bottom")
        }
        .frame(width: contentWidth, height: totalContentHeight, alignment: .topLeading)
        .clipped()

        GeometryReader { geometry in
            let viewportHeight = geometry.size.height
            
            ScrollViewReader { proxy in
            if #available(iOS 17.0, *) {
                ScrollView(.vertical, showsIndicators: false) {
                    content
                }
                .scrollBounceBehavior(.basedOnSize)
                .clipped()
                .onAppear {
                    scrollViewProxy = proxy
                        // Delay scroll until layout is ready - use Task to wait for next frame
                        Task { @MainActor in
                            try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 seconds
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                                hourHeight: hourHeight,
                                viewportHeight: viewportHeight,
                                modalBottomPadding: modalBottomPadding
                    )
                        }
                }
                .onChange(of: focusEvent?.eventID) {
                        // Delay scroll until layout is ready - use Task to wait for next frame
                        Task { @MainActor in
                            try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 seconds
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                                hourHeight: hourHeight,
                                viewportHeight: viewportHeight,
                                modalBottomPadding: modalBottomPadding
                    )
                        }
                }
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    content
                }
                .clipped()
                .onAppear {
                    scrollViewProxy = proxy
                        // Delay scroll until layout is ready - use Task to wait for next frame
                        Task { @MainActor in
                            try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 seconds
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                                hourHeight: hourHeight,
                                viewportHeight: viewportHeight,
                                modalBottomPadding: modalBottomPadding
                    )
                        }
                }
                .onChange(of: focusEvent?.eventID) {
                        // Delay scroll until layout is ready - use Task to wait for next frame
                        Task { @MainActor in
                            try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 seconds
                    scrollToFocusEventIfNeeded(
                        proxy: proxy,
                        gridHeight: gridHeight,
                        timelineTopInset: timelineTopInset,
                                hourHeight: hourHeight,
                                viewportHeight: viewportHeight,
                                modalBottomPadding: modalBottomPadding
                    )
                        }
                    }
                }
            }
        }
    }

    private func hourLabel(for hour: Int) -> String {
        switch hour {
        case 0:
            return "12AM"
        case 1..<12:
            return "\(hour)AM"
        case 12:
            return "12PM"
        case 13..<24:
            return "\(hour - 12)PM"
        default:
            return "12AM"
        }
    }
    
    private static func calculateTimeLabelWidth() -> CGFloat {
        // Calculate width needed for the longest time label
        // Longest labels are "12AM", "12PM", "10AM", "10PM" (4 characters)
        // Using .caption font size (typically 12pt) with medium weight
        let font = UIFont.preferredFont(forTextStyle: .caption1)
        let fontWithWeight = UIFont.systemFont(ofSize: font.pointSize, weight: .medium)
        let longestLabel = "12PM"
        let attributes: [NSAttributedString.Key: Any] = [.font: fontWithWeight]
        let size = (longestLabel as NSString).size(withAttributes: attributes)
        return ceil(size.width) + 2 // Add small padding
    }
    
    private func scrollToFocusEventIfNeeded(
        proxy: ScrollViewProxy,
        gridHeight: CGFloat,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat,
        viewportHeight: CGFloat,
        modalBottomPadding: CGFloat
    ) {
        guard let focusEvent else {
            // No focus event - scroll to 12:00 pm if we haven't already
            if !hasScrolledToNoon {
                scrollToTimeDiscrete(
                    hour: 12.0,
                    proxy: proxy,
                    viewportHeight: viewportHeight,
                    gridHeight: gridHeight,
                    modalBottomPadding: modalBottomPadding,
                    timelineTopInset: timelineTopInset,
                    hourHeight: hourHeight
                )
                hasScrolledToNoon = true
            }
            lastScrolledFocusEventID = nil
            return
        }
        
        // Reset noon scroll flag when we have a focus event
        hasScrolledToNoon = false
        
        // Avoid scrolling multiple times for the same event
        if lastScrolledFocusEventID == focusEvent.eventID {
            return
        }
        
        // Find the event directly in the events array
        guard let displayEvent = events.first(where: { $0.id == focusEvent.eventID }) else {
            return
        }
        
        // For all-day events, scroll to top (all-day section is already visible at top)
        if displayEvent.event.isAllDay {
            // All-day events are already visible at the top, no scrolling needed
            lastScrolledFocusEventID = focusEvent.eventID
            return
        }
        
        // Use original event start time directly
        guard let eventStartTime = displayEvent.event.start?.dateTime else {
            return
        }
        
        // Calculate which day this event starts on (relative to startDate)
        let eventStartOfDay = calendar.startOfDay(for: eventStartTime)
        let viewStartOfDay = calendar.startOfDay(for: startDate)
        
        // Use the start of the visible range if event starts before it
        let startOfDay = max(eventStartOfDay, viewStartOfDay)
        
        // Calculate hour offset within the day
        let startComponents = calendar.dateComponents([.minute, .second], from: startOfDay, to: eventStartTime)
        guard let startMinutes = startComponents.minute else { return }
        let startSeconds = Double(startComponents.second ?? 0)
        let eventStartHour = (Double(startMinutes) + startSeconds / 60) / 60
        
        // Scroll to position the event's start time at 1/3 from the top
        scrollToTimeDiscrete(
            hour: eventStartHour,
            proxy: proxy,
            viewportHeight: viewportHeight,
            gridHeight: gridHeight,
            modalBottomPadding: modalBottomPadding,
            timelineTopInset: timelineTopInset,
            hourHeight: hourHeight
        )
        
        lastScrolledFocusEventID = focusEvent.eventID
    }
    
    private func scrollToTimeDiscrete(
        hour: Double,
        proxy: ScrollViewProxy,
        viewportHeight: CGFloat,
        gridHeight: CGFloat,
        modalBottomPadding: CGFloat,
        timelineTopInset: CGFloat,
        hourHeight: CGFloat
    ) {
        // Round to nearest 15 minutes (discrete anchor interval)
        let anchorInterval: Double = 0.25  // 15 minutes in hours
        let roundedHour = (hour / anchorInterval).rounded() * anchorInterval
        // Normalize anchor ID format to match anchor creation (must use "hour-%.2f" format)
        let anchorID = String(format: "hour-%.2f", roundedHour)
        
        // Calculate where this anchor appears in content space
        let anchorY = timelineTopInset + hourHeight * CGFloat(roundedHour)
        
        // Target: position this time at 1/4 from viewport top
        let targetY = viewportHeight / 6.0
        let totalContentHeight = gridHeight + modalBottomPadding
        
        // Edge case: if event is too early to position at targetY, scroll to very top
        // This ensures the very top of the view is visible (above padding)
        if anchorY < targetY {
            // Too close to top - scroll to top anchor to show very top of view
            let topAnchorID = "scroll-top"
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 150_000_000) // 0.15 seconds
        withAnimation(.easeInOut(duration: 0.3)) {
                    proxy.scrollTo(topAnchorID, anchor: .top)
                }
            }
            return
        }
        
        // Edge case: if event is too late to position at targetY, scroll to very bottom
        // This ensures the very bottom of the view is visible (including padding)
        let maxScrollableOffset = max(0, totalContentHeight - viewportHeight)
        if anchorY - targetY > maxScrollableOffset {
            // Too close to bottom - scroll to bottom anchor to show very bottom of view
            let bottomAnchorID = "scroll-bottom"
            
            // Use Task with delay to ensure anchors are ready
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 150_000_000) // 0.15 seconds
                withAnimation(.easeInOut(duration: 0.3)) {
                    proxy.scrollTo(bottomAnchorID, anchor: .top)
                }
            }
            return
        }
        
        // For normal case - Calculate which anchor to scroll to achieve ~1/6 positioning
        // We want the target anchor at Y=anchorY to appear at viewport Y=targetY (1/6 from top)
        // If we scroll to an anchor at position Y=scrollAnchorY using .top:
        //   - scrollAnchorY appears at viewport Y=0
        //   - target anchor at Y=anchorY appears at viewport Y = (anchorY - scrollAnchorY)
        // We want: anchorY - scrollAnchorY = targetY
        // So: scrollAnchorY = anchorY - targetY
        let desiredScrollAnchorY = anchorY - targetY
        
        // Find the anchor closest to this calculated Y position
        // CRITICAL: Ensure desiredScrollAnchorY is valid - if it's too small, we'd scroll to top
        guard desiredScrollAnchorY >= timelineTopInset else {
            // Fallback: just use target anchor with .top (not ideal but better than scrolling to hour-0)
            withAnimation(.easeInOut(duration: 0.3)) {
                proxy.scrollTo(anchorID, anchor: .top)
            }
            return
        }
        
        // Improved rounding: try both floor and ceiling, pick closest to 1/4 target
        // This reduces imprecision from rounding to 15-minute intervals
        let scrollAnchorHour = Double((desiredScrollAnchorY - timelineTopInset) / hourHeight)
        let roundedDown = (scrollAnchorHour / anchorInterval).rounded(.down) * anchorInterval
        let roundedUp = (scrollAnchorHour / anchorInterval).rounded(.up) * anchorInterval
        
        // Calculate which rounding gets closer to targetY (1/4)
        let anchorYDown = timelineTopInset + hourHeight * CGFloat(roundedDown)
        let anchorYUp = timelineTopInset + hourHeight * CGFloat(roundedUp)
        let viewportYDown = anchorY - anchorYDown
        let viewportYUp = anchorY - anchorYUp
        let errorDown = abs(viewportYDown - targetY)
        let errorUp = abs(viewportYUp - targetY)
        
        let scrollRoundedHour = errorDown < errorUp ? roundedDown : roundedUp
        
        // Ensure scrollRoundedHour is valid (non-negative, reasonable)
        guard scrollRoundedHour >= 0 && scrollRoundedHour < 24 else {
            withAnimation(.easeInOut(duration: 0.3)) {
                proxy.scrollTo(anchorID, anchor: .top)
            }
            return
        }
        
        // Format anchor ID to match exact format used in anchor creation (normalized format)
        let scrollAnchorID = String(format: "hour-%.2f", scrollRoundedHour)
        
        // Try scrolling to anchor - increase delay to ensure anchors are fully rendered
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 150_000_000) // 0.15 seconds
            withAnimation(.easeInOut(duration: 0.3)) {
                proxy.scrollTo(scrollAnchorID, anchor: .top)
            }
        }
    }


    private func getTimezoneAbbreviation(from ianaName: String?) -> String {
        let timezone: TimeZone
        if let ianaName = ianaName, let tz = TimeZone(identifier: ianaName) {
            timezone = tz
        } else {
            timezone = TimeZone.autoupdatingCurrent
        }
        
        if let abbreviation = timezone.abbreviation() {
            // Remove offset (e.g., "EST-5" -> "EST")
            return String(abbreviation.prefix(3))
        }
        return "UTC"
    }
    
    static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.dateFormat = "EEE M/d"
        return formatter
    }()

    static let timeRangeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale.autoupdatingCurrent
        formatter.timeStyle = .short
        formatter.dateStyle = .none
        return formatter
    }()
    
    // MARK: - All-Day Event Row Packing
    
    fileprivate func getDayIndices(for segment: EventSegmentCard, dates: [Date]) -> [Int] {
        if segment.isSpanning {
            // For spanning events, find all overlapping day indices
            guard let startDateString = segment.event.event.start?.date else {
                return []
            }
            
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            dateFormatter.timeZone = calendar.timeZone
            
            guard let eventStartDate = dateFormatter.date(from: startDateString) else {
                return []
            }
            
            let eventStartOfDay = calendar.startOfDay(for: eventStartDate)
            
            let eventEndDate: Date
            if let endDateString = segment.event.event.end?.date,
               let parsedEndDate = dateFormatter.date(from: endDateString) {
                eventEndDate = calendar.startOfDay(for: parsedEndDate)
            } else {
                eventEndDate = calendar.date(byAdding: .day, value: 1, to: eventStartOfDay) ?? eventStartOfDay
            }
            
            var dayIndices: [Int] = []
            for (index, day) in dates.enumerated() {
                let startOfDay = calendar.startOfDay(for: day)
                guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
                    continue
                }
                if eventStartOfDay < endOfDay && eventEndDate > startOfDay {
                    dayIndices.append(index)
                }
            }
            return dayIndices
        } else {
            // For non-spanning events, return single day index
            if let dayIndex = dates.firstIndex(where: { calendar.isDate($0, inSameDayAs: segment.day) }) {
                return [dayIndex]
            }
            return []
        }
    }
    
    fileprivate func packAllDayEventsIntoRows(_ segments: [EventSegmentCard], dates: [Date]) -> [AllDayEventRow] {
        var rows: [AllDayEventRow] = []
        var rowOccupiedDays: [[Int]] = [] // Track which day indices each row occupies
        
        // Separate spanning and non-spanning
        let spanning = segments.filter { $0.isSpanning }
        let nonSpanning = segments.filter { !$0.isSpanning }
        
        // Step 1: Place spanning events (each on its own row)
        for (index, segment) in spanning.enumerated() {
            let dayIndices = getDayIndices(for: segment, dates: dates)
            rows.append(AllDayEventRow(segments: [segment], rowIndex: index))
            rowOccupiedDays.append(dayIndices)
        }
        
        // Step 2: Pack non-spanning events
        for segment in nonSpanning {
            let dayIndices = getDayIndices(for: segment, dates: dates)
            
            // Find first row where this event doesn't overlap
            var placed = false
            for (rowIndex, occupiedDays) in rowOccupiedDays.enumerated() {
                if !dayIndices.overlaps(with: occupiedDays) {
                    // Add to existing row
                    rows[rowIndex].segments.append(segment)
                    rowOccupiedDays[rowIndex].append(contentsOf: dayIndices)
                    placed = true
                    break
                }
            }
            
            if !placed {
                // Create new row
                let newRowIndex = rows.count
                rows.append(AllDayEventRow(segments: [segment], rowIndex: newRowIndex))
                rowOccupiedDays.append(dayIndices)
            }
        }
        
        return rows
    }
}

extension Array where Element == Int {
    func overlaps(with other: [Int]) -> Bool {
        return !Set(self).isDisjoint(with: Set(other))
    }
}

private extension NDayScheduleView {
    struct EventSegmentCard: Identifiable {
        let id: String  // Unique per segment: "\(event.id)-\(dayIndex)" for tracking
        let event: DisplayEvent  // Original event
        let eventID: String  // event.id - shared across all segments of same event
        let day: Date  // The day this segment represents
        let startTime: Date?  // Segment start (clamped to day boundaries)
        let endTime: Date?  // Segment end (clamped to day boundaries)
        let isAllDay: Bool  // Whether this is an all-day segment
        let isSpanning: Bool  // Whether this all-day event spans multiple columns
        let spanDays: Int?  // Number of days spanned (for all-day only)
    }
    
    struct AllDayEventRow {
        var segments: [EventSegmentCard]
        let rowIndex: Int
    }
    
    struct EventLayout {
        let startHour: Double
        let endHour: Double
        let durationHours: Double
        let title: String
        let timeRange: String
        let shouldShowTimeRange: Bool
        let style: ScheduleEventCard.Style
    }
    
    // MARK: - Segment Card Generation
    
    func generateSegmentCards(from events: [DisplayEvent], dates: [Date]) -> [EventSegmentCard] {
        var segments: [EventSegmentCard] = []
        
        for event in events where !event.isHidden {
            if event.event.isAllDay {
                // All-day: single segment card
                if let segment = createAllDaySegmentCard(event, dates: dates) {
                    segments.append(segment)
                }
            } else {
                // Timed: split into day segments
                segments.append(contentsOf: splitTimedEventToSegments(event, dates: dates))
            }
        }
        
        return segments
    }
    
    func splitTimedEventToSegments(_ event: DisplayEvent, dates: [Date]) -> [EventSegmentCard] {
        guard let startDateTime = event.event.start?.dateTime,
              let endDateTime = event.event.end?.dateTime else {
            return []
        }
        
        var segments: [EventSegmentCard] = []
        
        for (index, day) in dates.enumerated() {
            let startOfDay = calendar.startOfDay(for: day)
            guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
                continue
            }
            
            // Check if event overlaps this day
            if startDateTime < endOfDay && endDateTime > startOfDay {
                // Calculate clamped start/end times for this day
                let segmentStartTime = max(startDateTime, startOfDay)
                let segmentEndTime = min(endDateTime, endOfDay)
                
                let segmentID = "\(event.id)-\(index)"
                let segment = EventSegmentCard(
                    id: segmentID,
                    event: event,
                    eventID: event.id,
                    day: day,
                    startTime: segmentStartTime,
                    endTime: segmentEndTime,
                    isAllDay: false,
                    isSpanning: false,
                    spanDays: nil
                )
                segments.append(segment)
            }
        }
        
        return segments
    }
    
    func createAllDaySegmentCard(_ event: DisplayEvent, dates: [Date]) -> EventSegmentCard? {
        guard event.event.isAllDay else {
            return nil
        }
        
        guard let startDateString = event.event.start?.date else {
            return nil
        }
        
        // Parse date string (format: "YYYY-MM-DD")
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateFormatter.timeZone = calendar.timeZone
        
        guard let eventStartDate = dateFormatter.date(from: startDateString) else {
            return nil
        }
        
        // All-day events start at the beginning of the start date
        let eventStartOfDay = calendar.startOfDay(for: eventStartDate)
        
        // Calculate end date (exclusive - all-day event ends at start of next day)
        let eventEndDate: Date
        if let endDateString = event.event.end?.date,
           let parsedEndDate = dateFormatter.date(from: endDateString) {
            // End date is exclusive, so use it as-is (it represents the start of the day after the event ends)
            eventEndDate = calendar.startOfDay(for: parsedEndDate)
        } else {
            // If no end date, event spans just one day
            eventEndDate = calendar.date(byAdding: .day, value: 1, to: eventStartOfDay) ?? eventStartOfDay
        }
        
        // Find overlapping days
        let overlappingDays = dates.filter { day in
            let startOfDay = calendar.startOfDay(for: day)
            guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
                return false
            }
            // Check if event overlaps this day (event starts before day ends, event ends after day starts)
            return eventStartOfDay < endOfDay && eventEndDate > startOfDay
        }
        
        guard let firstOverlappingDay = overlappingDays.first else {
            return nil
        }
        
        // Check if spanning multiple days
        let isSpanning = overlappingDays.count > 1
        let spanDays = isSpanning ? overlappingDays.count : nil
        
        // For all-day events, use the first overlapping day
        // startTime and endTime are nil for all-day events
        let segmentID = "\(event.id)-allday"
        return EventSegmentCard(
            id: segmentID,
            event: event,
            eventID: event.id,
            day: firstOverlappingDay,
            startTime: nil,
            endTime: nil,
            isAllDay: true,
            isSpanning: isSpanning,
            spanDays: spanDays
        )
    }

    func layoutInfo(for segment: EventSegmentCard, focusEvent: ScheduleFocusEvent?) -> EventLayout? {
        // All-day events are handled separately, not in timeline
        guard !segment.isAllDay else { return nil }
        
        guard let startTime = segment.startTime,
              let endTime = segment.endTime else {
            return nil
        }
        
        let startOfDay = calendar.startOfDay(for: segment.day)
        let startComponents = calendar.dateComponents([.minute, .second], from: startOfDay, to: startTime)
        let endComponents = calendar.dateComponents([.minute, .second], from: startOfDay, to: endTime)

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
        if let originalStart = segment.event.event.start?.dateTime,
           let originalEnd = segment.event.event.end?.dateTime {
            let formattedStart = Self.timeRangeFormatter.string(from: originalStart)
            let formattedEnd = Self.timeRangeFormatter.string(from: originalEnd)
            timeRange = "\(formattedStart) – \(formattedEnd)"
        } else {
            timeRange = ""
        }

        let title = segment.event.event.title?.isEmpty == false ? segment.event.event.title! : "Untitled Event"
        let shouldShowTimeRange = duration >= 1.0

        let style: ScheduleEventCard.Style
        if let focusEvent, focusEvent.eventID == segment.eventID {
            style = cardStyle(for: focusEvent.style)
        } else {
            style = cardStyle(for: segment.event.style)
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
        case .new:
            return .new
        }
    }
}
