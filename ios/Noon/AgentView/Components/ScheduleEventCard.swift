//
//  ScheduleEventCard.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct ScheduleEventCard: View {
    enum Style {
        case standard
        case highlight
        case destructive
    }

    let title: String
    let timeRange: String
    let showTimeRange: Bool
    let cornerRadius: CGFloat
    let style: Style

    private var backgroundStyle: AnyShapeStyle {
        switch style {
        case .standard:
            return AnyShapeStyle(ColorPalette.Surface.overlay.opacity(0.92))
        case .highlight:
            return AnyShapeStyle(
                ColorPalette.Semantic.highlightBackground
            )
        case .destructive:
            return AnyShapeStyle(ColorPalette.Surface.destructiveMuted)
        }
    }

    private var borderStyle: AnyShapeStyle {
        switch style {
        case .standard:
            return AnyShapeStyle(ColorPalette.Text.secondary.opacity(0.45))
        case .highlight:
            return AnyShapeStyle(
                ColorPalette.Gradients.highlightBorder
            )
        case .destructive:
            return AnyShapeStyle(ColorPalette.Text.secondary.opacity(0.6))
        }
    }

    private var shadowColor: Color {
        switch style {
        case .standard:
            return Color.black.opacity(0.15)
        case .highlight:
            return ColorPalette.Semantic.primary.opacity(0.25)
        case .destructive:
            return Color.black.opacity(0.18)
        }
    }

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(backgroundStyle)
            .overlay(alignment: .leading) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(textColor)
                        .strikethrough(style == .destructive, color: strikeColor)
                    if showTimeRange {
                        Text(timeRange)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(secondaryTextColor)
                            .strikethrough(style == .destructive, color: strikeColor)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .overlay {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(borderStyle, lineWidth: 1)
            }
            .shadow(color: shadowColor, radius: 14, x: 0, y: 10)
    }
}

private extension ScheduleEventCard {
    var textColor: Color {
        switch style {
        case .standard, .highlight:
            return ColorPalette.Text.primary
        case .destructive:
            return ColorPalette.Text.primary.opacity(0.55)
        }
    }

    var secondaryTextColor: Color {
        switch style {
        case .standard, .highlight:
            return ColorPalette.Text.secondary.opacity(0.75)
        case .destructive:
            return ColorPalette.Text.secondary.opacity(0.5)
        }
    }

    var strikeColor: Color {
        switch style {
        case .standard, .highlight:
            return .clear
        case .destructive:
            return ColorPalette.Text.secondary.opacity(0.7)
        }
    }
}

struct ScheduleEventCard_Previews: PreviewProvider {
    static var previews: some View {
        VStack(alignment: .leading, spacing: 20) {
            ScheduleEventCard(
                title: "Daily Standup",
                timeRange: "9:00 – 9:30 AM",
                showTimeRange: false,
                cornerRadius: 12,
                style: .standard
            )
            .frame(height: 48)

            ScheduleEventCard(
                title: "Product Review",
                timeRange: "11:00 AM – 12:15 PM",
                showTimeRange: true,
                cornerRadius: 12,
                style: .destructive
            )
            .frame(height: 80)

            ScheduleEventCard(
                title: "Investor Update",
                timeRange: "2:00 – 3:00 PM",
                showTimeRange: true,
                cornerRadius: 12,
                style: .highlight
            )
            .frame(height: 80)
        }
        .padding()
        .frame(maxWidth: 320)
        .background(ColorPalette.Surface.background.ignoresSafeArea())
        .previewLayout(.sizeThatFits)
    }
}

