//
//  ColorPalette.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import SwiftUI
import UIKit

enum ColorPalette {
    enum Semantic {
        /// Primary brand color for emphasis against dark backgrounds.
        static let primary = Color(
            .displayP3,
            red: 1.0,
            green: 0.56,
            blue: 0.24,
            opacity: 1.0
        )

        /// Secondary accents for less prominent interactive elements.
        static let secondary = Color(
            .displayP3,
            red: 0.64,
            green: 0.54,
            blue: 0.99,
            opacity: 1.0
        )

        /// Destructive actions and critical warnings.
        static let destructive = Color(
            .displayP3,
            red: 1.0,
            green: 0.32,
            blue: 0.33,
            opacity: 1.0
        )

        /// Positive status and confirmation states.
        static let success = Color(
            .displayP3,
            red: 0.31,
            green: 0.83,
            blue: 0.57,
            opacity: 1.0
        )

        /// Attention-grabbing warning tone without destructive intent.
        static let warning = Color(
            .displayP3,
            red: 1.0,
            green: 0.72,
            blue: 0.23,
            opacity: 1.0
        )

        /// Soft highlight background used for special calendar events.
        static let highlightBackground = Color(
            .displayP3,
            red: 1.0,
            green: 0.82,
            blue: 0.66,
            opacity: 0.92
        )

        /// Gradient starting hue for highlight borders.
        static let highlightBorderStart = Color(
            .displayP3,
            red: 1.0,
            green: 0.45,
            blue: 0.24,
            opacity: 1.0
        )

        /// Gradient ending hue for highlight borders.
        static let highlightBorderEnd = Color(
            .displayP3,
            red: 1.0,
            green: 0.32,
            blue: 0.2,
            opacity: 0.95
        )
    }

    enum Text {
        static let primary = dynamicColor(
            light: UIColor(
                displayP3Red: 0.08,
                green: 0.09,
                blue: 0.12,
                alpha: 1.0
            ),
            dark: UIColor(
                displayP3Red: 0.95,
                green: 0.95,
                blue: 0.98,
                alpha: 1.0
            )
        )

        static let secondary = dynamicColor(
            light: UIColor(
                displayP3Red: 0.37,
                green: 0.4,
                blue: 0.47,
                alpha: 1.0
            ),
            dark: UIColor(
                displayP3Red: 0.67,
                green: 0.7,
                blue: 0.77,
                alpha: 1.0
            )
        )

        static let inverted = dynamicColor(
            light: UIColor(
                displayP3Red: 0.95,
                green: 0.95,
                blue: 0.98,
                alpha: 1.0
            ),
            dark: UIColor(
                displayP3Red: 0.08,
                green: 0.09,
                blue: 0.12,
                alpha: 1.0
            )
        )
    }

    enum Surface {
        static let background = dynamicColor(
            light: UIColor(
                displayP3Red: 1.0,
                green: 1.0,
                blue: 1.0,
                alpha: 1.0
            ),
            dark: UIColor(
                displayP3Red: 0.0,
                green: 0.0,
                blue: 0.0,
                alpha: 1.0
            )
        )

        static let elevated = dynamicColor(
            light: UIColor(
                displayP3Red: 0.95,
                green: 0.96,
                blue: 0.98,
                alpha: 1.0
            ),
            dark: UIColor(
                displayP3Red: 0.12,
                green: 0.13,
                blue: 0.16,
                alpha: 1.0
            )
        )

        static let overlay = dynamicColor(
            light: UIColor(
                displayP3Red: 0.86,
                green: 0.88,
                blue: 0.93,
                alpha: 0.55
            ),
            dark: UIColor(
                displayP3Red: 0.24,
                green: 0.27,
                blue: 0.32,
                alpha: 0.55
            )
        )

        static let destructiveMuted = dynamicColor(
            light: UIColor(
                displayP3Red: 0.5,
                green: 0.52,
                blue: 0.56,
                alpha: 0.88
            ),
            dark: UIColor(
                displayP3Red: 0.32,
                green: 0.34,
                blue: 0.38,
                alpha: 0.9
            )
        )
    }

    enum Gradients {
        /// Brand-forward orangey gradient for key calls to action.
        static let primary = LinearGradient(
            gradient: Gradient(
                colors: [
                    Color(
                        .displayP3,
                        red: 1.0,
                        green: 0.48,
                        blue: 0.29,
                        opacity: 1.0
                    ),
                    Color(
                        .displayP3,
                        red: 1.0,
                        green: 0.68,
                        blue: 0.24,
                        opacity: 1.0
                    )
                ]
            ),
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )

        static let backgroundBase = LinearGradient(
            gradient: Gradient(
                colors: [
                    Surface.background,
                    dynamicColor(
                        light: UIColor(
                            displayP3Red: 0.98,
                            green: 0.98,
                            blue: 1.0,
                            alpha: 1.0
                        ),
                        dark: UIColor(
                            displayP3Red: 0.05,
                            green: 0.05,
                            blue: 0.09,
                            alpha: 1.0
                        )
                    )
                ]
            ),
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )

        static let backgroundAccentWarm = RadialGradient(
            gradient: Gradient(
                colors: [
                    dynamicColor(
                        light: UIColor(
                            displayP3Red: 1.0,
                            green: 0.83,
                            blue: 0.6,
                            alpha: 0.35
                        ),
                        dark: UIColor(
                            displayP3Red: 0.95,
                            green: 0.55,
                            blue: 0.32,
                            alpha: 0.25
                        )
                    ),
                    dynamicColor(
                        light: UIColor(
                            displayP3Red: 1.0,
                            green: 0.92,
                            blue: 0.83,
                            alpha: 0.0
                        ),
                        dark: UIColor(
                            displayP3Red: 0.3,
                            green: 0.22,
                            blue: 0.15,
                            alpha: 0.0
                        )
                    )
                ]
            ),
            center: .topLeading,
            startRadius: 20,
            endRadius: 260
        )

        static let backgroundAccentCool = RadialGradient(
            gradient: Gradient(
                colors: [
                    dynamicColor(
                        light: UIColor(
                            displayP3Red: 0.77,
                            green: 0.87,
                            blue: 0.97,
                            alpha: 0.35
                        ),
                        dark: UIColor(
                            displayP3Red: 0.34,
                            green: 0.49,
                            blue: 0.71,
                            alpha: 0.25
                        )
                    ),
                    dynamicColor(
                        light: UIColor(
                            displayP3Red: 0.9,
                            green: 0.95,
                            blue: 0.99,
                            alpha: 0.0
                        ),
                        dark: UIColor(
                            displayP3Red: 0.12,
                            green: 0.17,
                            blue: 0.24,
                            alpha: 0.0
                        )
                    )
                ]
            ),
            center: .bottomTrailing,
            startRadius: 10,
            endRadius: 300
        )

        static let highlightBorder = LinearGradient(
            gradient: Gradient(
                colors: [
                    Semantic.highlightBorderStart,
                    Semantic.highlightBorderEnd
                ]
            ),
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }
}

private extension ColorPalette {
    static func dynamicColor(light: UIColor, dark: UIColor) -> Color {
        Color(
            UIColor { traitCollection in
                switch traitCollection.userInterfaceStyle {
                case .dark:
                    return dark
                case .light, .unspecified:
                    fallthrough
                @unknown default:
                    return light
                }
            }
        )
    }
}
