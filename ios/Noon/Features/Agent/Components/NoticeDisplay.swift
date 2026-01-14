//
//  NoticeDisplay.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

struct NoticeDisplay: View {
    let message: String?
    
    var body: some View {
        if let message = message, !message.isEmpty {
            Text(message)
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
            NoticeDisplay(message: "This is a sample notice message")
        }
    }
}
