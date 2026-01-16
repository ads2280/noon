//
//  MicrophoneButtonContainer.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

struct MicrophoneButtonContainer<Content: View>: View {
    let content: Content
    private let cornerRadius: CGFloat = 22
    private let horizontalPadding: CGFloat = 4 // Match schedule view horizontal padding
    private let verticalPadding: CGFloat = 12 // Top and bottom padding inside container
    private let buttonHeight: CGFloat = 72
    
    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }
    
    var body: some View {
        HStack(spacing: 0) {
            Spacer()
                .frame(width: horizontalPadding)
            
            VStack(spacing: 0) {
                Spacer()
                    .frame(height: verticalPadding)
                
                content
                
                Spacer()
                    .frame(height: verticalPadding)
            }
            .frame(height: buttonHeight + verticalPadding * 2) // Total height: button + padding top + padding bottom
            .frame(maxWidth: .infinity)
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: cornerRadius))
            .shadow(
                color: Color.black.opacity(0.1),
                radius: 12,
                x: 0,
                y: 4
            )
            
            Spacer()
                .frame(width: horizontalPadding)
        }
    }
}

#Preview {
    ZStack {
        ColorPalette.Gradients.backgroundBase
            .ignoresSafeArea()
        
        VStack {
            Spacer()
            MicrophoneButtonContainer {
                Button {
                    // Preview action
                } label: {
                    Capsule()
                        .fill(ColorPalette.Gradients.primary)
                        .frame(width: 196, height: 72)
                        .overlay {
                            Image(systemName: "mic.fill")
                                .font(.system(size: 32, weight: .semibold))
                                .foregroundStyle(ColorPalette.Text.inverted)
                        }
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .padding()
    }
}
