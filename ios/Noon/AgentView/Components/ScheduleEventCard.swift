//
//  ScheduleEventCard.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct ScheduleEventCard: View {
    let title: String
    let timeRange: String
    let showTimeRange: Bool
    let cornerRadius: CGFloat

    private let backgroundColor = ColorPalette.Surface.overlay.opacity(0.92)
    private let borderColor = ColorPalette.Text.secondary.opacity(0.45)
    private let shadowColor = Color.black.opacity(0.15)

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(backgroundColor)
            .overlay(alignment: .leading) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(ColorPalette.Text.primary)
                    if showTimeRange {
                        Text(timeRange)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(ColorPalette.Text.secondary.opacity(0.75))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .overlay {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(borderColor, lineWidth: 1)
            }
            .shadow(color: shadowColor, radius: 14, x: 0, y: 10)
    }
}

struct ScheduleEventCard_Previews: PreviewProvider {
    static var previews: some View {
        VStack(alignment: .leading, spacing: 20) {
            ScheduleEventCard(
                title: "Daily Standup",
                timeRange: "9:00 – 9:30 AM",
                showTimeRange: false,
                cornerRadius: 12
            )
            .frame(height: 48)

            ScheduleEventCard(
                title: "Product Review",
                timeRange: "11:00 AM – 12:15 PM",
                showTimeRange: true,
                cornerRadius: 12
            )
            .frame(height: 80)
        }
        .padding()
        .frame(maxWidth: 320)
        .background(ColorPalette.Surface.background.ignoresSafeArea())
        .previewLayout(.sizeThatFits)
    }
}

