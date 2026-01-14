//
//  TranscriptionDisplay.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

struct TranscriptionDisplay: View {
    let text: String?
    
    var body: some View {
        if let text = text, !text.isEmpty {
            Text(text)
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(ColorPalette.Text.secondary)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
                .padding(.bottom, 32)
                .transition(.opacity)
        }
    }
}

#Preview {
    ZStack {
        ColorPalette.Gradients.backgroundBase
            .ignoresSafeArea()
        
        VStack {
            Spacer()
            TranscriptionDisplay(text: "This is a sample transcription text")
        }
    }
}
