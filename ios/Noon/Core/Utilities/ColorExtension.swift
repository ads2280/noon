//
//  ColorExtension.swift
//  Noon
//
//  Color utilities for parsing hex color strings from calendar APIs
//

import SwiftUI

extension Color {
    /// Creates a Color from a hex string (e.g., "#0088aa" or "0088aa").
    /// Returns a neutral gray if the hex string is invalid or missing.
    static func fromHex(_ hex: String?) -> Color {
        guard let hex = hex?.trimmingCharacters(in: .whitespacesAndNewlines),
              !hex.isEmpty else {
            return Color.gray.opacity(0.5)
        }
        
        var cleanedHex = hex
        if cleanedHex.hasPrefix("#") {
            cleanedHex = String(cleanedHex.dropFirst())
        }
        
        // Validate hex format (should be 6 characters, all hex digits)
        guard cleanedHex.count == 6,
              cleanedHex.allSatisfy({ $0.isHexDigit }) else {
            return Color.gray.opacity(0.5)
        }
        
        // Parse RGB components
        let r = Double(Int(cleanedHex.prefix(2), radix: 16) ?? 0) / 255.0
        let g = Double(Int(cleanedHex.prefix(4).suffix(2), radix: 16) ?? 0) / 255.0
        let b = Double(Int(cleanedHex.suffix(2), radix: 16) ?? 0) / 255.0
        
        return Color(.displayP3, red: r, green: g, blue: b, opacity: 1.0)
    }
}

private extension Character {
    var isHexDigit: Bool {
        return ("0"..."9").contains(self) || ("a"..."f").contains(self.lowercased())
    }
}
