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
        switch style {
        case .standard:
            return AnyShapeStyle(ColorPalette.Surface.overlay)
        case .highlight, .update:
            return AnyShapeStyle(
                ColorPalette.Semantic.highlightBackground
            )
        case .new:
            return AnyShapeStyle(Color.white)
        case .destructive:
            return AnyShapeStyle(ColorPalette.Surface.destructiveMuted)
        }
    }

    private var shadowColor: Color {
        switch style {
        case .standard:
            return Color.black.opacity(0.15)
        case .highlight, .update, .new:
            return ColorPalette.Semantic.primary.opacity(0.25)
        case .destructive:
            return Color.black.opacity(0.18)
        }
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)

        let shadowConfiguration = shadowAttributes

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
                        .strikethrough(style == .destructive, color: strikeColor)
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
            .shadow(
                color: shadowConfiguration.color,
                radius: shadowConfiguration.radius,
                x: shadowConfiguration.x,
                y: shadowConfiguration.y
            )
    }

    private var shadowAttributes: (color: Color, radius: CGFloat, x: CGFloat, y: CGFloat) {
        guard style != .standard else { return (.clear, 0, 0, 0) }
        return (shadowColor, 14, 0, 10)
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
        switch style {
        case .standard:
            shape.stroke(ColorPalette.Text.secondary.opacity(0.45), lineWidth: 1)
        case .highlight:
            shape.stroke(ColorPalette.Gradients.highlightBorder, lineWidth: 1)
        case .update, .new:
            shape
                .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [6, 4]))
                .foregroundStyle(ColorPalette.Gradients.highlightBorder)
        case .destructive:
            shape.stroke(ColorPalette.Text.secondary.opacity(0.6), lineWidth: 1)
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

