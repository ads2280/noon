//
//  ConfirmationModal.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

enum ConfirmationActionType {
    case createEvent
    case deleteEvent
    case updateEvent
}

struct ConfirmationModal: View {
    let actionType: ConfirmationActionType
    let onConfirm: () -> Void
    let onCancel: () -> Void
    @Binding var isLoading: Bool
    
    private let buttonSize: CGFloat = 64
    
    var body: some View {
        // Two circular buttons side by side
        HStack(spacing: 24) {
            // Cancel button (left) - circular destructive muted outline with transparent interior
            Button {
                onCancel()
            } label: {
                ZStack {
                    Circle()
                        .stroke(ColorPalette.Surface.destructiveMuted, lineWidth: 2)
                        .frame(width: buttonSize, height: buttonSize)
                    
                    Image(systemName: "xmark")
                        .font(.system(size: 24, weight: .semibold))
                        .foregroundStyle(ColorPalette.Surface.destructiveMuted)
                }
            }
            .disabled(isLoading)
            
            // Confirm button (right) - circular orange gradient checkmark
            Button {
                onConfirm()
            } label: {
                ZStack {
                    Circle()
                        .fill(ColorPalette.Gradients.primary)
                        .frame(width: buttonSize, height: buttonSize)
                    
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(ColorPalette.Text.inverted)
                    } else {
                        Image(systemName: "checkmark")
                            .font(.system(size: 24, weight: .semibold))
                            .foregroundStyle(ColorPalette.Text.inverted)
                    }
                }
            }
            .disabled(isLoading)
        }
        .padding(.horizontal, 24)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }
}

#Preview {
    ZStack {
        ColorPalette.Gradients.backgroundBase
            .ignoresSafeArea()
        
        VStack {
            Spacer()
            ConfirmationModal(
                actionType: .createEvent,
                onConfirm: {},
                onCancel: {},
                isLoading: .constant(false)
            )
        }
    }
}
