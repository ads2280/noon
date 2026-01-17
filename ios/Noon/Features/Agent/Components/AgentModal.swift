//
//  AgentModal.swift
//  Noon
//
//  Created by Auto on 12/12/25.
//

import SwiftUI

enum AgentModalState {
    case confirmation(
        actionType: ConfirmationActionType,
        onConfirm: () -> Void,
        onCancel: () -> Void,
        isLoading: Bool
    )
    case thinking(text: String)
    case notice(message: String)
    case error(message: String, context: String)
}

struct AgentModal: View {
    let state: AgentModalState?
    
    private let fixedHeight: CGFloat = 88
    private let cornerRadius: CGFloat = 22
    private let horizontalPadding: CGFloat = 24 // Match schedule view horizontal padding
    private let verticalPadding: CGFloat = 20
    private let buttonSize: CGFloat = 64
    private let buttonSpacing: CGFloat = 24
    
    var body: some View {
        if let state = state {
            HStack(spacing: 0) {
                Spacer()
                    .frame(width: horizontalPadding)
                
                ZStack {
                    // Content layer
                    content(for: state)
                }
                .frame(height: fixedHeight)
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
            .transition(.opacity.combined(with: .move(edge: .bottom)))
        }
    }
    
    @ViewBuilder
    private func content(for state: AgentModalState) -> some View {
        switch state {
        case .confirmation(_, let onConfirm, let onCancel, let isLoading):
            HStack(spacing: buttonSpacing) {
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
            .frame(maxWidth: .infinity)
            
        case .thinking(let text):
            Text(text)
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(ColorPalette.Text.secondary)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .padding(.horizontal, horizontalPadding)
                .padding(.vertical, verticalPadding)
            
        case .notice(let message):
            Text(message)
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(ColorPalette.Text.secondary)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .padding(.horizontal, horizontalPadding)
                .padding(.vertical, verticalPadding)
            
        case .error(let message, let context):
            Text("\(context): \(message)")
                .font(.system(size: 14, weight: .regular))
                .foregroundColor(ColorPalette.Text.secondary)
                .lineLimit(2)
                .truncationMode(.tail)
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .padding(.horizontal, horizontalPadding)
                .padding(.vertical, verticalPadding)
        }
    }
}

#Preview {
    ZStack {
        ColorPalette.Gradients.backgroundBase
            .ignoresSafeArea()
        
        VStack(spacing: 32) {
            AgentModal(
                state: AgentModalState.confirmation(
                    actionType: .createEvent,
                    onConfirm: {},
                    onCancel: {},
                    isLoading: false
                )
            )
            
            AgentModal(
                state: AgentModalState.thinking(text: "This is a sample thinking text that might be truncated")
            )
            
            AgentModal(
                state: AgentModalState.notice(message: "This is a sample notice message")
            )
        }
        .padding()
    }
}
