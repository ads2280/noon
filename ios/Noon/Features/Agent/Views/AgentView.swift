//
//  AgentView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import SwiftUI
import UIKit

struct AgentView: View {
    @StateObject private var viewModel = AgentViewModel()
    @State private var isPressingMic = false

    @EnvironmentObject private var authViewModel: AuthViewModel
    @State private var isLoading = false
    @State private var didConfigureViewModel = false

    var body: some View {
        ZStack(alignment: .top) {
            ColorPalette.Gradients.backgroundBase
                .ignoresSafeArea()

            if viewModel.hasLoadedSchedule {
                NDayScheduleView(
                    startDate: viewModel.scheduleDate,
                    numberOfDays: viewModel.numberOfDays,
                    events: viewModel.displayEvents,
                    focusEvent: viewModel.focusEvent,
                    userTimezone: viewModel.userTimezone,
                    modalBottomPadding: scheduleModalPadding
                )
                .padding(.horizontal, 4)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 0) {
                // Reduced top spacing to bring schedule view closer to microphone button
                Color.clear
                    .frame(height: 8)
                
                // Microphone button - always in fixed position at bottom
                microphoneButton
                    .padding(.horizontal, 24)
            }
        }
        .overlay(alignment: .bottom) {
            // Unified modal appears above microphone button, overlaying the schedule view
            // Priority: confirmation > thinking > notice
            if let modalState = agentModalState {
                GeometryReader { geometry in
                    AgentModal(state: modalState)
                        .padding(.horizontal, 24)
                        .padding(.bottom, geometry.safeAreaInsets.bottom + 8 + 72 + 20 + 8) // safe area + spacing + button + padding + gap above schedule
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                }
            }
        }
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: agentModalState != nil)
        .onReceive(viewModel.$displayState) { state in
            handleDisplayStateChange(state)
        }
        .task {
            if didConfigureViewModel == false {
                viewModel.configure(authProvider: authViewModel)
                didConfigureViewModel = true
                try? await viewModel.loadCurrentDaySchedule()
            }
        }
        .onDisappear {
            // Cleanup audio session when view disappears to free up resources
            viewModel.cleanupAudioSession()
        }
    }

    private var agentModalState: AgentModalState? {
        // Priority: confirmation > thinking > notice
        // Only show confirmation once schedule is ready AND transcription is cleared to ensure smooth transition
        if let agentAction = viewModel.agentAction, 
           agentAction.requiresConfirmation, 
           viewModel.hasLoadedSchedule, 
           viewModel.transcriptionText == nil {
            return .confirmation(
                actionType: actionType(for: agentAction),
                onConfirm: {
                    Task {
                        await viewModel.confirmPendingAction(accessToken: authViewModel.session?.accessToken)
                    }
                },
                onCancel: {
                    viewModel.cancelPendingAction()
                },
                isLoading: viewModel.isConfirmingAction
            )
        } else if let transcriptionText = viewModel.transcriptionText, !transcriptionText.isEmpty {
            return .thinking(text: transcriptionText)
        } else if let noticeMessage = viewModel.noticeMessage, !noticeMessage.isEmpty {
            return .notice(message: noticeMessage)
        } else {
            return nil
        }
    }
    
    private var scheduleModalPadding: CGFloat? {
        agentModalState != nil ? 120 : nil // modal height (88) + gap (8) + buffer (24)
    }
    
    private var microphoneButton: some View {
        Button {
            // Intentionally empty; gesture handles interaction
        } label: {
            Capsule()
                .fill(ColorPalette.Gradients.primary)
                .frame(width: 196, height: 72)
                .shadow(
                    color: ColorPalette.Semantic.primary.opacity(0.35),
                    radius: 24,
                    x: 0,
                    y: 12
                )
                .overlay {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(ColorPalette.Text.inverted)
                    } else {
                        Image(systemName: "mic.fill")
                            .font(.system(size: 32, weight: .semibold))
                            .foregroundStyle(ColorPalette.Text.inverted)
                    }
                }
                .frame(maxWidth: .infinity)
        }
        .scaleEffect(viewModel.isRecording ? 1.05 : 1.0)
        .opacity(viewModel.isRecording ? 0.85 : 1.0)
        .buttonStyle(.plain)
        .onLongPressGesture(
            minimumDuration: 0,
            maximumDistance: 80,
            pressing: { pressing in
                if pressing && isPressingMic == false {
                    isPressingMic = true
                    // Haptic feedback when mic starts listening
                    let generator = UIImpactFeedbackGenerator(style: .medium)
                    generator.prepare()
                    generator.impactOccurred()
                    viewModel.startRecording()
                } else if pressing == false && isPressingMic {
                    isPressingMic = false
                    // Haptic feedback when releasing the button
                    let generator = UIImpactFeedbackGenerator(style: .medium)
                    generator.prepare()
                    generator.impactOccurred()
                    viewModel.stopAndSendRecording(accessToken: authViewModel.session?.accessToken)
                }
            },
            perform: {}
        )
        .padding(.bottom, 20)
    }

    private func actionType(for agentAction: AgentViewModel.AgentAction) -> ConfirmationActionType {
        switch agentAction {
        case .createEvent:
            return .createEvent
        case .deleteEvent:
            return .deleteEvent
        case .updateEvent:
            return .updateEvent
        case .showEvent, .showSchedule:
            // These shouldn't reach here since requiresConfirmation is false
            return .createEvent
        }
    }

    private func handleDisplayStateChange(_ state: AgentViewModel.DisplayState) {
        switch state {
        case .recording:
            isLoading = false
        case .uploading:
            isLoading = true
        case .completed:
            isLoading = false
        case .failed(_):
            isLoading = false
        case .idle:
            isLoading = false
        }
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
