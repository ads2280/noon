//
//  MicrophoneButtonContainer.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

struct MicrophoneButtonContainer<Content: View>: View {
    let content: Content
    private let buttonWidth: CGFloat = 196
    private let buttonHeight: CGFloat = 72
    private let padding: CGFloat = 12 // Same padding on all sides
    
    private var containerHeight: CGFloat {
        buttonHeight + padding * 2
    }
    
    private var cornerRadius: CGFloat {
        containerHeight / 2 // Fully rounded edges (capsule shape)
    }
    
    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }
    
    var body: some View {
        HStack {
            Spacer()
            
            VStack(spacing: 0) {
                Spacer()
                    .frame(height: padding)
                
                content
                
                Spacer()
                    .frame(height: padding)
            }
            .frame(width: buttonWidth + padding * 2) // Container width: button + padding on each side
            .frame(height: containerHeight) // Container height: button + padding top + bottom
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: cornerRadius))
            .shadow(
                color: Color.black.opacity(0.1),
                radius: 12,
                x: 0,
                y: 4
            )
            
            Spacer()
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
                }
            }
        }
        .padding()
    }
}
