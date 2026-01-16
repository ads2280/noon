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
                        .lineLimit(1)
                        .minimumScaleFactor(0.85)
                        .frame(maxWidth: .infinity, alignment: .leading)
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
        let baseHorizontalPadding: CGFloat = 12
        let baseVerticalPadding: CGFloat = 8

        let titleLineHeight = UIFont.preferredFont(forTextStyle: .caption1).lineHeight
        let contentHeight = titleLineHeight

        let remainingHeight = availableHeight - contentHeight

        let topPadding: CGFloat
        let bottomPadding: CGFloat

        if remainingHeight <= (baseVerticalPadding * 2) {
            let equalPadding = max(remainingHeight / 2, 0)
            topPadding = equalPadding
            bottomPadding = equalPadding
        } else {
            topPadding = baseVerticalPadding
            bottomPadding = remainingHeight - baseVerticalPadding
        }

        return ContentMetrics(
            topPadding: topPadding,
            bottomPadding: bottomPadding,
            horizontalPadding: baseHorizontalPadding
        )
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

