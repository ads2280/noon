//
//  ScheduleEventCard.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI
import UIKit

struct ScheduleEventCard: View {
    enum Style {
        case standard
        case highlight
        case update
        case destructive
        case new
    }

    let title: String
    let cornerRadius: CGFloat
    let style: Style
    let calendarColor: Color?
    
    init(title: String, cornerRadius: CGFloat, style: Style, calendarColor: Color? = nil) {
        self.title = title
        self.cornerRadius = cornerRadius
        self.style = style
        self.calendarColor = calendarColor
    }
    
    // Text rendering thresholds (based on caption font line height ~17px)
    private static let multilineThreshold: CGFloat = 38   // >= 38px: multiline, < 38px: single line
    private static let scaledFontThreshold: CGFloat = 12  // 18-17px: single line, scaled font
    private static let reducedPaddingThreshold: CGFloat = 12  // 12-17px: scaled font, reduced padding
    // < 12px: just clip whatever fits
    
    // Padding constants
    // Calculate fullPadding to allow 2 lines in 1-hour event (38px height)
    private static var fullPadding: CGFloat {
        let font = UIFont.preferredFont(forTextStyle: .caption1)
        let fontWithWeight = UIFont.systemFont(ofSize: font.pointSize, weight: .semibold)
        let lineHeight = fontWithWeight.lineHeight
        let oneHourHeight: CGFloat = 38  // 40px hourHeight - 2px verticalEventInset
        let twoLinesHeight = lineHeight * 2
        return max(2, (oneHourHeight - twoLinesHeight) / 2)
    }
    private static let reducedPadding: CGFloat = 4
    private static let horizontalPaddingValue: CGFloat = 8

    private var backgroundStyle: AnyShapeStyle {
        // For new style, always use white/system background
        if style == .new {
            return AnyShapeStyle(Color.white)
        }
        
        // If calendar color is provided, use it with appropriate opacity
        // Make highlight/update styles more prominent (higher opacity for more drastic change)
        // Make destructive style darker (higher opacity)
        if let calendarColor = calendarColor {
            let opacity: CGFloat
            if style == .highlight || style == .update {
                opacity = 0.22  // Increased from 0.12 for more drastic background color change
            } else if style == .destructive {
                opacity = 0.3  // Darker for destructive style
            } else {
                opacity = 0.2
            }
            return AnyShapeStyle(calendarColor.opacity(opacity))
        }
        
        // For destructive style without calendar color, use darker muted color
        if style == .destructive {
            return AnyShapeStyle(ColorPalette.Surface.destructiveMuted)
        }
        
        // Otherwise, use the gray overlay color (default for regular cards)
        return AnyShapeStyle(ColorPalette.Surface.overlay)
    }

    private var shadowColor: Color {
        // If calendar color is provided, use it for shadow
        if let calendarColor = calendarColor {
            return calendarColor.opacity(0.25)
        }
        
        // Otherwise, use subtle black shadow (same as default standard cards)
        return Color.black.opacity(0.15)
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)

        let shadowConfiguration = shadowAttributes

        ZStack {
            // Glow layer - appears behind the card
            glowOverlay
            
            // Card layers
            shape
                .fill(ColorPalette.Surface.background)
                .overlay {
                    shape.fill(backgroundStyle)
                }
                .overlay(alignment: .topLeading) {
                    GeometryReader { proxy in
                        let metrics = contentMetrics(for: proxy.size.height)

                        Text(title)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(textColor)
                            .lineLimit(metrics.maxLines)
                            .minimumScaleFactor(metrics.maxLines == 1 ? metrics.fontScale : 1.0)
                            .fixedSize(horizontal: false, vertical: metrics.maxLines != 1)
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                            .padding(.horizontal, metrics.horizontalPadding)
                            .padding(.top, metrics.topPadding)
                            .padding(.bottom, metrics.bottomPadding)
                            .frame(width: proxy.size.width, height: proxy.size.height, alignment: .topLeading)
                    }
                    .clipShape(shape)
                }
                .overlay { borderOverlay }
                .overlay { crosshatchOverlay }
        }
        .shadow(
            color: shadowConfiguration.color,
            radius: shadowConfiguration.radius,
            x: shadowConfiguration.x,
            y: shadowConfiguration.y
        )
    }

    private var shadowAttributes: (color: Color, radius: CGFloat, x: CGFloat, y: CGFloat) {
        // Always use shadow with the appropriate color (calendar color or default black)
        // Standard style cards still get a shadow, just more subtle
        let radius: CGFloat = style == .standard ? 8 : 14
        let y: CGFloat = style == .standard ? 5 : 10
        return (shadowColor, radius, 0, y)
    }
}

private extension ScheduleEventCard {
    struct ContentMetrics {
        let topPadding: CGFloat
        let bottomPadding: CGFloat
        let horizontalPadding: CGFloat
        let maxLines: Int?
        let fontScale: CGFloat
        let shouldTruncate: Bool
    }

    var textColor: Color {
        switch style {
        case .standard, .highlight, .update, .new:
            return ColorPalette.Text.primary
        case .destructive:
            return ColorPalette.Text.primary.opacity(0.55)
        }
    }

    var secondaryTextColor: Color {
        switch style {
        case .standard, .highlight, .update, .new:
            return ColorPalette.Text.secondary.opacity(0.75)
        case .destructive:
            return ColorPalette.Text.secondary.opacity(0.5)
        }
    }

    var strikeColor: Color {
        switch style {
        case .standard, .highlight, .update, .new:
            return .clear
        case .destructive:
            return ColorPalette.Text.secondary.opacity(0.7)
        }
    }

    @ViewBuilder
    var borderOverlay: some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        // Use muted destructive color for destructive style, otherwise use calendar color
        let borderColor: Color = style == .destructive
            ? ColorPalette.Surface.destructiveMuted
            : (calendarColor ?? ColorPalette.Text.secondary.opacity(0.45))
        
        // Use dashed border for update/new styles, solid for others
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
    var glowOverlay: some View {
        // Add glow effect for new, highlight, and update styles
        // This appears behind the card, creating a glow effect around the edges
        if (style == .new || style == .highlight || style == .update), let calendarColor = calendarColor {
            let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            // Create an outer glow effect using a blurred stroke with increased intensity
            // The glow extends beyond the card bounds and appears behind it
            shape
                .stroke(calendarColor.opacity(0.75), lineWidth: 4)  // Increased opacity from 0.5 to 0.75, lineWidth from 3 to 4
                .blur(radius: 8)  // Increased blur radius from 6 to 8 for more intense glow
        } else {
            // Empty view when glow is not needed
            Color.clear
        }
    }
    
    @ViewBuilder
    var crosshatchOverlay: some View {
        // Add diagonal lines pattern for destructive style
        if style == .destructive {
            let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            // Use muted destructive color for crosshatch
            let crosshatchColor = ColorPalette.Surface.destructiveMuted
            
            GeometryReader { geometry in
                let size = geometry.size
                let lineSpacing: CGFloat = 7  // Increased spacing for a more open crosshatch pattern
                let lineWidth: CGFloat = 1
                // Lines at 45 degrees: slope = 1 (going from bottom-left to top-right)
                // In screen coordinates, this means: y = -x + c (since y increases downward)
                // Or equivalently: y = height - x + intercept (where intercept is at x=0)
                
                Canvas { context, canvasSize in
                    // Draw evenly spaced parallel lines at 45 degrees
                    // Line equation: y = -x + intercept (in screen coords, so -x for 45° up-right)
                    // We'll iterate through intercept values
                    let maxDimension = max(size.width, size.height)
                    var intercept: CGFloat = -maxDimension
                    while intercept < size.width + size.height {
                        var path = Path()
                        
                        var startPoint: CGPoint?
                        var endPoint: CGPoint?
                        
                        // Line equation: y = -x + intercept (45 degrees, bottom-left to top-right)
                        // Convert to screen coords: y = size.height - x + intercept
                        // Actually, let's use: y = intercept - x (offset to screen coords later)
                        
                        // Check intersections with card edges
                        // Intersection with left edge (x = 0): y = intercept
                        if intercept >= 0 && intercept <= size.height {
                            startPoint = CGPoint(x: 0, y: intercept)
                        }
                        
                        // Intersection with bottom edge (y = size.height): x = intercept - size.height
                        let xAtBottom = intercept - size.height
                        if xAtBottom >= 0 && xAtBottom <= size.width {
                            if startPoint == nil {
                                startPoint = CGPoint(x: xAtBottom, y: size.height)
                            } else {
                                endPoint = CGPoint(x: xAtBottom, y: size.height)
                            }
                        }
                        
                        // Intersection with right edge (x = size.width): y = intercept - size.width
                        let yAtRight = intercept - size.width
                        if yAtRight >= 0 && yAtRight <= size.height {
                            if endPoint == nil {
                                endPoint = CGPoint(x: size.width, y: yAtRight)
                            }
                        }
                        
                        // Intersection with top edge (y = 0): x = intercept
                        if intercept >= 0 && intercept <= size.width {
                            if endPoint == nil {
                                endPoint = CGPoint(x: intercept, y: 0)
                            }
                        }
                        
                        // Draw the line if we have both endpoints
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

    func contentMetrics(for availableHeight: CGFloat) -> ContentMetrics {
        let font = UIFont.preferredFont(forTextStyle: .caption1)
        let fontWithWeight = UIFont.systemFont(ofSize: font.pointSize, weight: .semibold)
        let actualLineHeight = fontWithWeight.lineHeight
        
        // Determine rendering mode based on available height
        if availableHeight >= Self.multilineThreshold {
            // Multiline: show as many lines as fit, full padding, full font, with truncation
            let topPadding = Self.fullPadding - 2  // Reduce by 1px to compensate for visual difference
            let bottomPadding = Self.fullPadding + 2
            let horizontalPadding = Self.horizontalPaddingValue
            let availableTextHeight = availableHeight - topPadding - bottomPadding
            let maxLines = max(1, Int(floor(availableTextHeight / actualLineHeight)))
            let fontScale: CGFloat = 1.0
            let shouldTruncate = true
            
            return ContentMetrics(
                topPadding: topPadding,
                bottomPadding: bottomPadding,
                horizontalPadding: horizontalPadding,
                maxLines: maxLines,
                fontScale: fontScale,
                shouldTruncate: shouldTruncate
            )
        } else if availableHeight < Self.multilineThreshold {
            // Single line full: full padding, single line, full font
            let horizontalPadding = Self.horizontalPaddingValue
            let maxLines = 1
            let fontScale: CGFloat = 1.0
            let shouldTruncate = true
            
            // Adjust padding to center the single line
            let contentHeight = actualLineHeight
            let remainingHeight = availableHeight - contentHeight
            let topPadding: CGFloat
            let bottomPadding: CGFloat
            if remainingHeight <= (Self.fullPadding * 2) {
                let equalPadding = max(remainingHeight / 2, 0)
                topPadding = equalPadding
                bottomPadding = equalPadding
            } else {
                topPadding = Self.fullPadding
                bottomPadding = remainingHeight - Self.fullPadding
            }
            
            return ContentMetrics(
                topPadding: topPadding,
                bottomPadding: bottomPadding,
                horizontalPadding: horizontalPadding,
                maxLines: maxLines,
                fontScale: fontScale,
                shouldTruncate: shouldTruncate
            )
        } else if availableHeight >= Self.scaledFontThreshold {
            // Single line scaled: full padding, single line, scaled font
            let horizontalPadding = Self.horizontalPaddingValue
            let maxLines = 1
            let fontScale: CGFloat = 0.85
            let shouldTruncate = true
            
            // Adjust padding to center the single line
            let contentHeight = actualLineHeight * fontScale
            let remainingHeight = availableHeight - contentHeight
            let topPadding: CGFloat
            let bottomPadding: CGFloat
            if remainingHeight <= (Self.fullPadding * 2) {
                let equalPadding = max(remainingHeight / 2, 0)
                topPadding = equalPadding
                bottomPadding = equalPadding
            } else {
                topPadding = Self.fullPadding
                bottomPadding = remainingHeight - Self.fullPadding
            }
            
            return ContentMetrics(
                topPadding: topPadding,
                bottomPadding: bottomPadding,
                horizontalPadding: horizontalPadding,
                maxLines: maxLines,
                fontScale: fontScale,
                shouldTruncate: shouldTruncate
            )
        } else if availableHeight >= Self.reducedPaddingThreshold {
            // Scaled with reduced padding: reduced padding, single line, scaled font
            let horizontalPadding = Self.horizontalPaddingValue
            let maxLines = 1
            let fontScale: CGFloat = 0.85
            let shouldTruncate = true
            
            // Adjust padding to fit
            let contentHeight = actualLineHeight * fontScale
            let remainingHeight = availableHeight - contentHeight
            let topPadding: CGFloat
            let bottomPadding: CGFloat
            if remainingHeight <= (Self.reducedPadding * 2) {
                let equalPadding = max(remainingHeight / 2, 0)
                topPadding = equalPadding
                bottomPadding = equalPadding
            } else {
                topPadding = Self.reducedPadding
                bottomPadding = remainingHeight - Self.reducedPadding
            }
            
            return ContentMetrics(
                topPadding: topPadding,
                bottomPadding: bottomPadding,
                horizontalPadding: horizontalPadding,
                maxLines: maxLines,
                fontScale: fontScale,
                shouldTruncate: shouldTruncate
            )
        } else {
            // Minimum: minimal padding, single line, scaled font, clip
            let topPadding = max(availableHeight * 0.1, 0)
            let bottomPadding = max(availableHeight * 0.1, 0)
            let horizontalPadding = Self.horizontalPaddingValue
            let maxLines = 1
            let fontScale: CGFloat = 0.85
            let shouldTruncate = true
            
            return ContentMetrics(
                topPadding: topPadding,
                bottomPadding: bottomPadding,
                horizontalPadding: horizontalPadding,
                maxLines: maxLines,
                fontScale: fontScale,
                shouldTruncate: shouldTruncate
            )
        }
    }
}

struct ScheduleEventCard_Previews: PreviewProvider {
    static var previews: some View {
        VStack(alignment: .leading, spacing: 20) {
            ScheduleEventCard(
                title: "Daily Standup",
                cornerRadius: 12,
                style: .standard
            )
            .frame(height: 48)

            ScheduleEventCard(
                title: "Product Review",
                cornerRadius: 12,
                style: .destructive
            )
            .frame(height: 80)

            ScheduleEventCard(
                title: "Investor Update",
                cornerRadius: 12,
                style: .highlight
            )
            .frame(height: 80)

            ScheduleEventCard(
                title: "AI Strategy Session",
                cornerRadius: 12,
                style: .update
            )
            .frame(height: 80)
        }
        .padding()
        .frame(maxWidth: 320)
        .background(ColorPalette.Surface.background.ignoresSafeArea())
        .previewLayout(.sizeThatFits)
    }
}

