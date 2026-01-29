//
//  SwipeableScheduleView.swift
//  Noon
//
//  Created by Auto on 1/27/26.
//

import SwiftUI
import UIKit
import Foundation

// MARK: - All-Day Event Data Structures

private struct AllDaySegmentCard: Identifiable {
    let id: String                    // Unique: "\(event.id)-allday"
    let event: DisplayEvent           // Original event
    let eventID: String               // event.id
    let eventStartDay: Date           // First day of event (normalized)
    let eventEndDay: Date             // Exclusive end day (normalized)
    let isSpanning: Bool              // Spans multiple days?
    let spanDays: Int                 // Number of days spanned
}

private struct AllDayEventRow {
    var segments: [AllDaySegmentCard]
    let rowIndex: Int
}

// MARK: - Sticky Title All-Day Card

/// A custom all-day event card with a sticky title that stays visible when scrolling
private struct StickyTitleAllDayCard: View {
    let title: String
    let calendarColor: Color?
    let style: ScheduleEventCard.Style
    let titleOffset: CGFloat
    
    private let cornerRadius: CGFloat = 5
    private let horizontalPadding: CGFloat = 8
    
    var body: some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        let shadowConfig = shadowAttributes
        
        ZStack {
            // Glow layer - appears behind the card
            glowOverlay
            
            // Card layers
            shape
                .fill(ColorPalette.Surface.background)
                .overlay {
                    shape.fill(backgroundStyle)
                }
                .overlay(alignment: .leading) {
                    // Sticky title - offset to stay in visible area, clipped to card bounds
                    Text(title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(textColor)
                        .lineLimit(1)
                        .padding(.horizontal, horizontalPadding)
                        .offset(x: titleOffset)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .clipShape(shape)
                }
                .overlay { borderOverlay }
                .overlay { crosshatchOverlay }
        }
        .shadow(
            color: shadowConfig.color,
            radius: shadowConfig.radius,
            x: shadowConfig.x,
            y: shadowConfig.y
        )
    }
    
    private var backgroundStyle: some ShapeStyle {
        if style == .new {
            return AnyShapeStyle(ColorPalette.Surface.background)
        }
        
        if let calendarColor = calendarColor {
            let opacity: CGFloat
            if style == .highlight || style == .update {
                opacity = 0.45
            } else if style == .destructive {
                opacity = 0.3
            } else {
                opacity = 0.2
            }
            return AnyShapeStyle(calendarColor.opacity(opacity))
        }
        
        if style == .destructive {
            return AnyShapeStyle(ColorPalette.Surface.destructiveMuted)
        }
        
        return AnyShapeStyle(ColorPalette.Surface.overlay)
    }
    
    private var textColor: Color {
        switch style {
        case .standard, .highlight, .update, .new:
            return ColorPalette.Text.primary
        case .destructive:
            return ColorPalette.Text.primary.opacity(0.55)
        }
    }
    
    private var shadowColor: Color {
        if let calendarColor = calendarColor {
            return calendarColor.opacity(0.25)
        }
        return Color.black.opacity(0.15)
    }
    
    private var shadowAttributes: (color: Color, radius: CGFloat, x: CGFloat, y: CGFloat) {
        let radius: CGFloat = style == .standard ? 8 : 14
        let y: CGFloat = style == .standard ? 5 : 10
        return (shadowColor, radius, 0, y)
    }
    
    @ViewBuilder
    private var borderOverlay: some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        let borderColor: Color = style == .destructive
            ? ColorPalette.Surface.destructiveMuted
            : (calendarColor ?? ColorPalette.Text.secondary.opacity(0.45))
        
        switch style {
        case .update, .new:
            shape
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [6, 4]))
                .foregroundStyle(borderColor)
        default:
            shape.stroke(borderColor, lineWidth: 1)
        }
    }
    
    @ViewBuilder
    private var glowOverlay: some View {
        if (style == .new || style == .highlight || style == .update), let calendarColor = calendarColor {
            let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            shape
                .stroke(calendarColor.opacity(0.75), lineWidth: 4)
                .blur(radius: 8)
        } else {
            Color.clear
        }
    }
    
    @ViewBuilder
    private var crosshatchOverlay: some View {
        if style == .destructive {
            let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            let crosshatchColor = ColorPalette.Surface.destructiveMuted
            
            GeometryReader { geometry in
                let size = geometry.size
                let lineSpacing: CGFloat = 7
                let lineWidth: CGFloat = 1
                
                Canvas { context, _ in
                    let maxDimension = max(size.width, size.height)
                    var intercept: CGFloat = -maxDimension
                    while intercept < size.width + size.height {
                        var path = Path()
                        var startPoint: CGPoint?
                        var endPoint: CGPoint?
                        
                        if intercept >= 0 && intercept <= size.height {
                            startPoint = CGPoint(x: 0, y: intercept)
                        }
                        
                        let xAtBottom = intercept - size.height
                        if xAtBottom >= 0 && xAtBottom <= size.width {
                            if startPoint == nil {
                                startPoint = CGPoint(x: xAtBottom, y: size.height)
                            } else {
                                endPoint = CGPoint(x: xAtBottom, y: size.height)
                            }
                        }
                        
                        let yAtRight = intercept - size.width
                        if yAtRight >= 0 && yAtRight <= size.height {
                            if endPoint == nil {
                                endPoint = CGPoint(x: size.width, y: yAtRight)
                            }
                        }
                        
                        if intercept >= 0 && intercept <= size.width {
                            if endPoint == nil {
                                endPoint = CGPoint(x: intercept, y: 0)
                            }
                        }
                        
                        if let start = startPoint, let end = endPoint {
                            path.move(to: start)
                            path.addLine(to: end)
                            context.stroke(path, with: .color(crosshatchColor), lineWidth: lineWidth)
                        }
                        
                        intercept += lineSpacing
                    }
                }
            }
            .clipShape(shape)
        }
    }
}

// MARK: - SwipeableScheduleView

struct SwipeableScheduleView: View {
    let referenceDate: Date  // Already normalized to start of day in init
    let numberOfDays: Int
    let userTimezone: String?
    let modalBottomPadding: CGFloat
    
    // Events and callbacks
    let events: [DisplayEvent]
    let onVisibleDaysChanged: ((Date) -> Void)?

    private let hours = Array(0..<24)
    
    // Day range: referenceDate ± 365 days
    private let dayRangeOffset: Int = 365
    private var totalDayCount: Int { dayRangeOffset * 2 + 1 }
    
    // Layout constants
    private let timelineTopInset: CGFloat = 6
    private let hourHeight: CGFloat = 40
    private let horizontalEventInset: CGFloat = 5
    private let verticalEventInset: CGFloat = 2
    private let minimumEventHeight: CGFloat = 20
    private let allDayEventHeight: CGFloat = 20
    private let allDayRowSpacing: CGFloat = 2
    private let allDayTopPadding: CGFloat = 4
    private let allDayBottomPadding: CGFloat = 2
    
    // Cached calendar instance (computed once in init)
    private let calendar: Calendar
    
    // Cached DateFormatter instances (expensive to create)
    private let dateHeaderFormatter: DateFormatter
    private let allDayDateFormatter: DateFormatter
    
    // Scroll position tracking
    @State private var scrolledDayIndex: Int?
    @State private var hasScrolledToInitial: Bool = false
    @State private var horizontalOffset: CGFloat = 0
    @State private var verticalOffset: CGFloat = 0
    @State private var scrollDebounceTask: Task<Void, Never>?
    
    // Cached all-day rows (updated only when events change)
    @State private var cachedAllDayRows: [AllDayEventRow] = []
    
    // normalizedReferenceDate is just referenceDate since it's already normalized in init
    private var normalizedReferenceDate: Date { referenceDate }
    
    private var initialDayIndex: Int {
        dayRangeOffset
    }
    
    init(
        referenceDate: Date,
        numberOfDays: Int = 3,
        events: [DisplayEvent] = [],
        userTimezone: String? = nil,
        modalBottomPadding: CGFloat = 0,
        onVisibleDaysChanged: ((Date) -> Void)? = nil
    ) {
        self.userTimezone = userTimezone
        self.events = events
        self.onVisibleDaysChanged = onVisibleDaysChanged
        
        // Create and cache calendar once
        if let userTimezone = userTimezone, let timeZone = TimeZone(identifier: userTimezone) {
            var cal = Calendar(identifier: .gregorian)
            cal.timeZone = timeZone
            self.calendar = cal
        } else {
            self.calendar = Calendar.autoupdatingCurrent
        }
        
        // Cache DateFormatters (expensive to create)
        let headerFormatter = DateFormatter()
        headerFormatter.locale = Locale.autoupdatingCurrent
        headerFormatter.dateFormat = "EEE M/d"
        headerFormatter.timeZone = self.calendar.timeZone
        self.dateHeaderFormatter = headerFormatter
        
        let allDayFormatter = DateFormatter()
        allDayFormatter.dateFormat = "yyyy-MM-dd"
        allDayFormatter.timeZone = self.calendar.timeZone
        self.allDayDateFormatter = allDayFormatter
        
        // Normalize reference date to start of day
        self.referenceDate = self.calendar.startOfDay(for: referenceDate)
        self.numberOfDays = max(1, numberOfDays)
        self.modalBottomPadding = modalBottomPadding
    }

    var body: some View {
        GeometryReader { geometry in
            let timeLabelAreaWidth = Self.calculateTimeLabelWidth()
            let labelSpacing: CGFloat = 8
            let gridLeading = timeLabelAreaWidth + labelSpacing
            let viewportWidth = geometry.size.width - gridLeading
            let dayColumnWidth = viewportWidth / CGFloat(numberOfDays)
            let gridHeight = timelineTopInset + hourHeight * CGFloat(hours.count)
            let lineColor = ColorPalette.Surface.overlay.opacity(1)
            let dateHeaderHeight: CGFloat = 18
            let paddingHeight = calculateBottomPadding()
            
            // Calculate all-day section height based on visible rows
            let visibleRange = visibleDayIndexRange(
                horizontalOffset: horizontalOffset,
                viewportWidth: viewportWidth,
                dayColumnWidth: dayColumnWidth
            )
            let viewportStart = -horizontalOffset
            let viewportEnd = viewportStart + viewportWidth
            let visibleRows = visibleAllDayRows(
                for: visibleRange,
                viewportStart: viewportStart,
                viewportEnd: viewportEnd,
                dayColumnWidth: dayColumnWidth
            )
            let allDaySectionHeight = calculateAllDaySectionHeight(rowCount: visibleRows.count)

            // Four-quadrant layout with nested scroll views
            HStack(alignment: .top, spacing: 0) {
                // LEFT COLUMN: Empty corner + All-day spacer + Row headers (hour labels)
                VStack(alignment: .leading, spacing: 0) {
                    // Top-left: Empty corner for date headers
                    Color.clear
                        .frame(width: gridLeading, height: dateHeaderHeight)
                    
                    // Spacer for all-day section (always present for animated height)
                    Color.clear
                        .frame(width: gridLeading, height: allDaySectionHeight)
                    
                    // Bottom-left: Row headers (hour labels) - synced with vertical offset
                    hourLabelsContent(
                        timeLabelAreaWidth: timeLabelAreaWidth,
                        gridHeight: gridHeight,
                        paddingHeight: paddingHeight
                    )
                    .offset(y: verticalOffset)
                    .clipped()
                }
                .frame(width: gridLeading)
                
                // RIGHT COLUMN: Column headers (date labels) + All-day section + Main grid
                VStack(alignment: .leading, spacing: 0) {
                    // Top-right: Column headers (date labels) - synced with horizontal offset
                    dateHeadersContent(
                        dayColumnWidth: dayColumnWidth
                    )
                    .offset(x: horizontalOffset)
                    .frame(width: viewportWidth, height: dateHeaderHeight, alignment: .leading)
                    .clipped()
                    
                    // All-day events section - synced with horizontal offset (always present for animated collapse)
                    allDayEventsSection(
                        rows: visibleRows,
                        dayColumnWidth: dayColumnWidth,
                        lineColor: lineColor,
                        horizontalOffset: horizontalOffset,
                        viewportWidth: viewportWidth
                    )
                    .offset(x: horizontalOffset)
                    .frame(width: viewportWidth, height: allDaySectionHeight, alignment: .topLeading)
                    .clipped()
                    
                    // Bottom-right: Nested scroll views for direction locking
                    // OUTER: Vertical ScrollView - handles up/down
                    ScrollView(.vertical, showsIndicators: false) {
                        // INNER: Horizontal ScrollView with snap - handles left/right
                        ScrollView(.horizontal, showsIndicators: false) {
                            LazyHStack(alignment: .top, spacing: 0) {
                                ForEach(0..<totalDayCount, id: \.self) { dayIndex in
                                    let dayDate = dateForDayIndex(dayIndex)
                                    let dayEvents = eventsForDay(dayDate)
                                    let isWeekend = isWeekendDay(dayDate)
                                    
                                    // Day column with grid lines and events
                                    ZStack(alignment: .topLeading) {
                                        // Weekend background tint
                                        if isWeekend {
                                            ColorPalette.Surface.weekendTint
                                                .frame(width: dayColumnWidth, height: gridHeight)
                                        }
                                        
                                        // Grid lines
                                        Canvas { context, _ in
                                            for index in 0...hours.count {
                                                let y = timelineTopInset + hourHeight * CGFloat(index)
                                                var path = Path()
                                                path.move(to: CGPoint(x: 0, y: y))
                                                path.addLine(to: CGPoint(x: dayColumnWidth, y: y))
                                                context.stroke(path, with: .color(lineColor), lineWidth: 1)
                                            }
                                        }
                                        .frame(width: dayColumnWidth, height: gridHeight)
                                        
                                        // Event cards (timed events only, exclude all-day)
                                        ForEach(dayEvents.filter { !$0.event.isAllDay }, id: \.id) { event in
                                            eventCard(
                                                for: event,
                                                on: dayDate,
                                                dayColumnWidth: dayColumnWidth,
                                                gridHeight: gridHeight
                                            )
                                        }
                                    }
                                    .frame(width: dayColumnWidth, height: gridHeight)
                                    .id(dayIndex)
                                }
                            }
                            .scrollTargetLayout()
                        }
                        .scrollTargetBehavior(.viewAligned)
                        .scrollPosition(id: $scrolledDayIndex, anchor: .leading)
                        .frame(height: gridHeight) // CRITICAL: explicit height for gesture pass-through
                        .onScrollGeometryChange(for: CGFloat.self) { geo in
                            geo.contentOffset.x
                        } action: { _, newValue in
                            horizontalOffset = -newValue
                        }
                        
                        // Bottom padding OUTSIDE inner scroll, INSIDE outer scroll
                        Color.clear
                            .frame(width: viewportWidth, height: paddingHeight)
                    }
                    .scrollBounceBehavior(.basedOnSize)
                    .onScrollGeometryChange(for: CGFloat.self) { geo in
                        geo.contentOffset.y
                    } action: { _, newValue in
                        verticalOffset = -newValue
                    }
                    .frame(width: viewportWidth)
                }
                .frame(width: viewportWidth)
            }
            .animation(.easeInOut(duration: 0.25), value: visibleRows.count)
            .onAppear {
                if !hasScrolledToInitial {
                    scrolledDayIndex = initialDayIndex
                    hasScrolledToInitial = true
                    // Notify initial visible date
                    let initialDate = dateForDayIndex(initialDayIndex)
                    onVisibleDaysChanged?(initialDate)
                }
                // Initialize cached all-day rows
                cachedAllDayRows = computeAllDayRows()
            }
            .onChange(of: events) { _, _ in
                // Recompute all-day rows when events change
                cachedAllDayRows = computeAllDayRows()
            }
            .onChange(of: scrolledDayIndex) { oldValue, newValue in
                // Debounce scroll position changes to avoid excessive callbacks
                scrollDebounceTask?.cancel()
                scrollDebounceTask = Task {
                    try? await Task.sleep(nanoseconds: 200_000_000)  // 200ms debounce
                    guard !Task.isCancelled, let dayIndex = newValue else { return }
                    let visibleDate = dateForDayIndex(dayIndex)
                    onVisibleDaysChanged?(visibleDate)
                }
            }
        }
        .padding(.top, 4)
        .ignoresSafeArea(edges: .bottom)
    }
    
    // MARK: - All-Day Events
    
    /// Create segment cards for all all-day events
    private func createAllDaySegments() -> [AllDaySegmentCard] {
        return events.filter { $0.event.isAllDay && !$0.isHidden }.compactMap { event in
            guard let startDateString = event.event.start?.date,
                  let eventStartDate = allDayDateFormatter.date(from: startDateString) else {
                return nil
            }
            
            let eventStartDay = calendar.startOfDay(for: eventStartDate)
            
            // Calculate end date (exclusive)
            let eventEndDay: Date
            if let endDateString = event.event.end?.date,
               let parsedEndDate = allDayDateFormatter.date(from: endDateString) {
                eventEndDay = calendar.startOfDay(for: parsedEndDate)
            } else {
                eventEndDay = calendar.date(byAdding: .day, value: 1, to: eventStartDay) ?? eventStartDay
            }
            
            // Calculate span days
            let spanDays = max(1, calendar.dateComponents([.day], from: eventStartDay, to: eventEndDay).day ?? 1)
            let isSpanning = spanDays > 1
            
            return AllDaySegmentCard(
                id: "\(event.id)-allday",
                event: event,
                eventID: event.id,
                eventStartDay: eventStartDay,
                eventEndDay: eventEndDay,
                isSpanning: isSpanning,
                spanDays: spanDays
            )
        }
    }
    
    /// Pack all-day events into rows using first-fit algorithm
    /// Events are sorted by start date (earliest first) and placed in the topmost row where they fit
    private func computeAllDayRows() -> [AllDayEventRow] {
        let segments = createAllDaySegments()
        guard !segments.isEmpty else { return [] }
        
        // Sort segments by start date (earliest first), then by end date (latest first) for ties
        let sortedSegments = segments.sorted { 
            if $0.eventStartDay == $1.eventStartDay {
                return $0.eventEndDay > $1.eventEndDay
            }
            return $0.eventStartDay < $1.eventStartDay
        }
        
        var rows: [AllDayEventRow] = []
        var rowOccupiedDays: [[Int]] = []
        
        // Place each segment in the topmost row where it fits
        for segment in sortedSegments {
            let dayIndices = getDayIndicesForAllDay(segment)
            var placed = false
            
            for (rowIndex, occupiedDays) in rowOccupiedDays.enumerated() {
                if !dayIndices.overlaps(with: occupiedDays) {
                    rows[rowIndex].segments.append(segment)
                    rowOccupiedDays[rowIndex].append(contentsOf: dayIndices)
                    placed = true
                    break
                }
            }
            
            if !placed {
                let newRowIndex = rows.count
                rows.append(AllDayEventRow(segments: [segment], rowIndex: newRowIndex))
                rowOccupiedDays.append(dayIndices)
            }
        }
        
        return rows
    }
    
    /// Get the day indices that an all-day segment occupies
    /// Optimized O(1) calculation instead of iterating all days
    private func getDayIndicesForAllDay(_ segment: AllDaySegmentCard) -> [Int] {
        // Calculate day offset from reference date using date math
        let startOffset = calendar.dateComponents([.day], from: normalizedReferenceDate, to: segment.eventStartDay).day ?? 0
        let endOffset = calendar.dateComponents([.day], from: normalizedReferenceDate, to: segment.eventEndDay).day ?? 0
        
        // Convert to indices (referenceDate is at index dayRangeOffset)
        let startIndex = max(0, dayRangeOffset + startOffset)
        let endIndex = min(totalDayCount, dayRangeOffset + endOffset)
        
        // Return array of indices in range
        guard startIndex < endIndex else { return [] }
        return Array(startIndex..<endIndex)
    }
    
    /// Get the current visible day index range based on scroll position.
    /// Base range is the n snapped days. Buffer days (1 left/right) are included only when
    /// any fraction of them is on screen (mid-swipe), so rows collapse correctly when fully snapped.
    private func visibleDayIndexRange(
        horizontalOffset: CGFloat,
        viewportWidth: CGFloat,
        dayColumnWidth: CGFloat
    ) -> Range<Int> {
        let currentIndex = scrolledDayIndex ?? initialDayIndex
        let viewportStart = -horizontalOffset
        let viewportEnd = viewportStart + viewportWidth

        let firstVisibleDayLeft = CGFloat(currentIndex) * dayColumnWidth
        let lastVisibleDayRight = CGFloat(currentIndex + numberOfDays) * dayColumnWidth

        let includeLeftBuffer = viewportStart < firstVisibleDayLeft
        let includeRightBuffer = viewportEnd > lastVisibleDayRight

        let start = includeLeftBuffer ? max(0, currentIndex - 1) : currentIndex
        let end = includeRightBuffer ? min(totalDayCount, currentIndex + numberOfDays + 1) : currentIndex + numberOfDays

        return start..<end
    }
    
    /// Filter rows to only those with events in the visible range, collapsing empty rows.
    /// Excludes segments whose drawn rect is entirely outside the viewport (avoids empty rows
    /// when an event is only in the left buffer and fully off-screen).
    private func visibleAllDayRows(
        for visibleRange: Range<Int>,
        viewportStart: CGFloat,
        viewportEnd: CGFloat,
        dayColumnWidth: CGFloat
    ) -> [AllDayEventRow] {
        let filteredRows = cachedAllDayRows.compactMap { row -> AllDayEventRow? in
            let visibleSegments = row.segments.filter { segment in
                let segmentDayIndices = getDayIndicesForAllDay(segment)
                guard segmentDayIndices.contains(where: { visibleRange.contains($0) }) else { return false }
                return segmentIntersectsViewport(
                    segment: segment,
                    viewportStart: viewportStart,
                    viewportEnd: viewportEnd,
                    dayColumnWidth: dayColumnWidth
                )
            }
            return visibleSegments.isEmpty ? nil : AllDayEventRow(segments: visibleSegments, rowIndex: row.rowIndex)
        }
        
        // Reassign row indices to collapse gaps
        return filteredRows.enumerated().map { (newIndex, row) in
            AllDayEventRow(segments: row.segments, rowIndex: newIndex)
        }
    }
    
    /// True iff the segment's drawn rect intersects [viewportStart, viewportEnd].
    private func segmentIntersectsViewport(
        segment: AllDaySegmentCard,
        viewportStart: CGFloat,
        viewportEnd: CGFloat,
        dayColumnWidth: CGFloat
    ) -> Bool {
        let dayIndices = getDayIndicesForAllDay(segment)
        guard let firstIndex = dayIndices.min() else { return false }
        let spanCount = segment.spanDays
        let cardWidth = CGFloat(spanCount) * dayColumnWidth - horizontalEventInset
        let offsetX = CGFloat(firstIndex) * dayColumnWidth + horizontalEventInset / 2
        let segmentLeft = offsetX
        let segmentRight = offsetX + cardWidth
        return segmentRight > viewportStart && segmentLeft < viewportEnd
    }
    
    /// Calculate the height of the all-day section based on row count
    private func calculateAllDaySectionHeight(rowCount: Int) -> CGFloat {
        guard rowCount > 0 else { return 0 }
        let rowHeight = allDayEventHeight + allDayRowSpacing
        return allDayTopPadding + CGFloat(rowCount) * rowHeight - allDayRowSpacing + allDayBottomPadding
    }
    
    /// Render the all-day events section
    @ViewBuilder
    private func allDayEventsSection(
        rows: [AllDayEventRow],
        dayColumnWidth: CGFloat,
        lineColor: Color,
        horizontalOffset: CGFloat,
        viewportWidth: CGFloat
    ) -> some View {
        let totalContentWidth = dayColumnWidth * CGFloat(totalDayCount)
        let rowHeight = allDayEventHeight + allDayRowSpacing
        
        ZStack(alignment: .topLeading) {
            // Render all-day event cards
            ForEach(rows, id: \.rowIndex) { row in
                Group {
                    ForEach(row.segments, id: \.id) { segment in
                        allDayEventCard(
                            segment: segment,
                            dayColumnWidth: dayColumnWidth,
                            horizontalOffset: horizontalOffset,
                            viewportWidth: viewportWidth
                        )
                        .offset(y: allDayTopPadding + CGFloat(row.rowIndex) * rowHeight)
                    }
                }
                .transition(.opacity)
            }
        }
        .frame(width: totalContentWidth, alignment: .topLeading)
    }
    
    /// Render an individual all-day event card with sticky title
    @ViewBuilder
    private func allDayEventCard(
        segment: AllDaySegmentCard,
        dayColumnWidth: CGFloat,
        horizontalOffset: CGFloat,
        viewportWidth: CGFloat
    ) -> some View {
        let dayIndices = getDayIndicesForAllDay(segment)
        if let firstIndex = dayIndices.min() {
            let spanCount = segment.spanDays
            let cardWidth = CGFloat(spanCount) * dayColumnWidth - horizontalEventInset
            let offsetX = CGFloat(firstIndex) * dayColumnWidth + horizontalEventInset / 2
            
            let title = segment.event.event.title?.isEmpty == false ? segment.event.event.title! : "Untitled Event"
            let calendarColor = segment.event.event.calendarColor.flatMap { Color.fromHex($0) }
            let style = cardStyle(for: segment.event.style)
            
            // Calculate sticky title offset
            let stickyOffset = calculateStickyTitleOffset(
                horizontalOffset: horizontalOffset,
                cardOffsetX: offsetX,
                cardWidth: cardWidth
            )
            
            StickyTitleAllDayCard(
                title: title,
                calendarColor: calendarColor,
                style: style,
                titleOffset: stickyOffset
            )
            .frame(width: cardWidth, height: allDayEventHeight)
            .offset(x: offsetX)
        }
    }
    
    // MARK: - Timed Event Rendering
    
    /// Filter events that occur on a specific day
    private func eventsForDay(_ date: Date) -> [DisplayEvent] {
        let dayStart = calendar.startOfDay(for: date)
        guard let dayEnd = calendar.date(byAdding: .day, value: 1, to: dayStart) else {
            return []
        }
        
        return events.filter { event in
            // Skip hidden events
            guard !event.isHidden else { return false }
            
            // For timed events, check if event overlaps this day
            if let startTime = event.event.start?.dateTime,
               let endTime = event.event.end?.dateTime {
                // Event overlaps day if: start < dayEnd AND end > dayStart
                return startTime < dayEnd && endTime > dayStart
            }
            
            // All-day events are handled separately
            return false
        }
    }
    
    /// Render an event card positioned based on its start/end time
    @ViewBuilder
    private func eventCard(
        for event: DisplayEvent,
        on dayDate: Date,
        dayColumnWidth: CGFloat,
        gridHeight: CGFloat
    ) -> some View {
        if let layout = eventLayout(for: event, on: dayDate, dayColumnWidth: dayColumnWidth) {
            let title = event.event.title?.isEmpty == false ? event.event.title! : "Untitled Event"
            let calendarColor = event.event.calendarColor.flatMap { Color.fromHex($0) }
            let style: ScheduleEventCard.Style = cardStyle(for: event.style)
            
            ScheduleEventCard(
                title: title,
                cornerRadius: 5,
                style: style,
                calendarColor: calendarColor
            )
            .frame(width: layout.width, height: layout.height)
            .offset(x: layout.offsetX, y: layout.offsetY)
        }
    }
    
    /// Calculate layout for an event on a specific day
    private func eventLayout(
        for event: DisplayEvent,
        on dayDate: Date,
        dayColumnWidth: CGFloat
    ) -> (width: CGFloat, height: CGFloat, offsetX: CGFloat, offsetY: CGFloat)? {
        guard let startTime = event.event.start?.dateTime,
              let endTime = event.event.end?.dateTime else {
            return nil
        }
        
        let dayStart = calendar.startOfDay(for: dayDate)
        guard let dayEnd = calendar.date(byAdding: .day, value: 1, to: dayStart) else {
            return nil
        }
        
        // Clamp event times to this day's boundaries
        let clampedStart = max(startTime, dayStart)
        let clampedEnd = min(endTime, dayEnd)
        
        // Calculate position as difference FROM start of day (not extracting time components)
        // This correctly handles midnight as 24 hours, not 0 hours
        // For multi-day events, this ensures middle days show the full 24-hour segment
        let startComponents = calendar.dateComponents([.minute, .second], from: dayStart, to: clampedStart)
        let endComponents = calendar.dateComponents([.minute, .second], from: dayStart, to: clampedEnd)
        
        guard let startMinutes = startComponents.minute,
              let endMinutes = endComponents.minute else {
            return nil
        }
        
        let startSeconds = Double(startComponents.second ?? 0)
        let endSeconds = Double(endComponents.second ?? 0)
        
        let startHour = (Double(startMinutes) + startSeconds / 60.0) / 60.0
        let endHour = (Double(endMinutes) + endSeconds / 60.0) / 60.0
        let durationHours = endHour - startHour
        
        guard durationHours > 0 else {
            return nil
        }
        
        let topOffset = timelineTopInset + hourHeight * CGFloat(startHour)
        let eventHeight = max(hourHeight * CGFloat(durationHours) - verticalEventInset, minimumEventHeight)
        let eventWidth = dayColumnWidth - horizontalEventInset
        
        return (
            width: eventWidth,
            height: eventHeight,
            offsetX: horizontalEventInset / 2,
            offsetY: topOffset
        )
    }
    
    /// Convert DisplayEvent style to ScheduleEventCard style
    private func cardStyle(for style: DisplayEvent.Style?) -> ScheduleEventCard.Style {
        switch style {
        case .highlight:
            return .highlight
        case .update:
            return .update
        case .destructive:
            return .destructive
        case .new:
            return .new
        case .none:
            return .standard
        }
    }
    
    // MARK: - Date Headers Content (Column Labels)
    
    @ViewBuilder
    private func dateHeadersContent(
        dayColumnWidth: CGFloat
    ) -> some View {
        // Use LazyHStack for performance - only renders visible date labels
        LazyHStack(alignment: .top, spacing: 0) {
            ForEach(0..<totalDayCount, id: \.self) { dayIndex in
                let date = dateForDayIndex(dayIndex)
                Text(dateHeaderFormatter.string(from: date))
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(ColorPalette.Text.secondary)
                    .frame(width: dayColumnWidth, height: 18, alignment: .leading)
            }
        }
    }
    
    // MARK: - Hour Labels Content (Row Labels)
    
    @ViewBuilder
    private func hourLabelsContent(
        timeLabelAreaWidth: CGFloat,
        gridHeight: CGFloat,
        paddingHeight: CGFloat
    ) -> some View {
        VStack(spacing: 0) {
            ZStack(alignment: .topTrailing) {
                Color.clear
                    .frame(width: timeLabelAreaWidth, height: gridHeight)
                
                ForEach(hours, id: \.self) { hour in
                    Text(hourLabel(for: hour))
                        .font(.caption.weight(.medium))
                        .foregroundStyle(ColorPalette.Text.secondary.opacity(0.9))
                        .frame(width: timeLabelAreaWidth, alignment: .trailing)
                        .position(
                            x: timeLabelAreaWidth / 2,
                            y: timelineTopInset + hourHeight * CGFloat(hour)
                        )
                }
            }
            .frame(width: timeLabelAreaWidth, height: gridHeight)
            
            // Bottom padding to match grid
            Color.clear
                .frame(width: timeLabelAreaWidth, height: paddingHeight)
        }
    }
    
    // MARK: - Bottom Padding
    
    private func calculateBottomPadding() -> CGFloat {
        let spaceToMicrophoneTop: CGFloat = 146
        let modalHeight: CGFloat = 88
        let modalMicrophoneGap: CGFloat = 8
        let baseMicrophonePadding: CGFloat = 96 + 8 + 24
        let isModalVisible = modalBottomPadding > baseMicrophonePadding
        return spaceToMicrophoneTop + (isModalVisible ? (modalHeight + modalMicrophoneGap) : 0)
    }
    
    // MARK: - Helpers
    
    private func dateForDayIndex(_ dayIndex: Int) -> Date {
        let offset = dayIndex - dayRangeOffset
        return calendar.date(byAdding: .day, value: offset, to: normalizedReferenceDate) ?? normalizedReferenceDate
    }
    
    /// Check if a date falls on a weekend (Saturday or Sunday)
    private func isWeekendDay(_ date: Date) -> Bool {
        let weekday = calendar.component(.weekday, from: date)
        // Sunday = 1, Saturday = 7
        return weekday == 1 || weekday == 7
    }
    
    private func hourLabel(for hour: Int) -> String {
        switch hour {
        case 0: return "12AM"
        case 1..<12: return "\(hour)AM"
        case 12: return "12PM"
        case 13..<24: return "\(hour - 12)PM"
        default: return "12AM"
        }
    }
    
    private static func calculateTimeLabelWidth() -> CGFloat {
        let font = UIFont.preferredFont(forTextStyle: .caption1)
        let fontWithWeight = UIFont.systemFont(ofSize: font.pointSize, weight: .medium)
        let longestLabel = "12PM"
        let attributes: [NSAttributedString.Key: Any] = [.font: fontWithWeight]
        let size = (longestLabel as NSString).size(withAttributes: attributes)
        return ceil(size.width) + 2
    }
    
    /// Calculate the offset needed to keep the title visible when card is partially off-screen
    private func calculateStickyTitleOffset(
        horizontalOffset: CGFloat,
        cardOffsetX: CGFloat,
        cardWidth: CGFloat
    ) -> CGFloat {
        // horizontalOffset is negative when scrolled right (viewing later days)
        // viewportStart is where the visible area begins in content coordinates
        let viewportStart = -horizontalOffset
        let titlePadding: CGFloat = 8  // Match ScheduleEventCard horizontal padding
        let minTitleWidth: CGFloat = 60  // Minimum space for title before it slides off right edge
        
        // If card's left edge is off-screen, push title right
        guard viewportStart > cardOffsetX else { return 0 }
        
        // Add horizontalEventInset/2 so the stuck title has the same visual margin
        // from the viewport edge as the natural title has from the card edge
        let insetOffset = horizontalEventInset / 2
        let rawOffset = viewportStart - cardOffsetX + insetOffset
        // Clamp so title doesn't go past the card's visible right edge
        let maxOffset = cardWidth - minTitleWidth - titlePadding
        return min(rawOffset, max(0, maxOffset))
    }
}

#Preview {
    SwipeableScheduleView(
        referenceDate: Date(),
        numberOfDays: 3,
        events: [],
        userTimezone: nil,
        modalBottomPadding: 0
    )
}
