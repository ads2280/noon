//
//  PhoneNumberFormatter.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/12/25.
//

import Foundation

enum PhoneNumberFormatter {
    static func formatDisplay(from input: String) -> String {
        let digitsOnly = input.filter(\.isNumber)

        guard digitsOnly.isEmpty == false else { return "" }

        var digits = digitsOnly

        if digits.count >= 11, digits.hasPrefix("1") {
            digits = String(digits.dropFirst())
        }

        if digits.count > 10 {
            digits = String(digits.prefix(10))
        }

        let area = String(digits.prefix(3))
        let middle = String(digits.dropFirst(min(3, digits.count)).prefix(3))
        let last = String(digits.dropFirst(min(6, digits.count)))

        var formatted = ""

        if area.isEmpty == false {
            formatted += "(\(area)"
            if area.count == 3 {
                formatted += ")"
                if digits.count > 3 {
                    formatted += " "
                }
            }
        }

        if middle.isEmpty == false {
            formatted += middle
            if middle.count == 3, last.isEmpty == false {
                formatted += " - "
            }
        }

        if last.isEmpty == false {
            formatted += last
        }

        return formatted
    }
}



