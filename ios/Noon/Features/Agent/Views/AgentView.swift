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
    @State private var selectedEventForDetails: CalendarEvent?
    @State private var isLoadingEventDetails = false

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
                    modalBottomPadding: scheduleModalPadding,
                    selectedEvent: $selectedEventForDetails,
                    onBackgroundTap: selectedEventForDetails != nil ? {
                        selectedEventForDetails = nil
                    } : nil
                )
                .padding(.horizontal, 4)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .ignoresSafeArea(edges: .bottom) // Extend schedule to bottom of screen
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .overlay(alignment: .top) {
            if let event = selectedEventForDetails {
                EventDetailsModal(event: event)
                    .padding(.top, 8)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .onChange(of: selectedEventForDetails) { oldValue, newValue in
            // When an event is selected, fetch full event details to ensure we have attendees, location, etc.
            if let event = newValue, event.calendarId != nil {
                Task {
                    await fetchFullEventDetails(event: event)
                }
            }
        }
        .onChange(of: viewModel.displayEvents) { oldValue, newValue in
            // Clear EventDetailsModal when schedule reloads with new events
            // This ensures the modal doesn't show stale event data
            // Only clear if we have a selected event and the events actually changed
            if selectedEventForDetails != nil && oldValue != newValue {
                selectedEventForDetails = nil
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 8) { // 4pt gap between modal and microphone container
                // Unified modal appears above microphone button, overlaying the schedule view
                // Priority: confirmation > thinking > notice
                if let modalState = agentModalState {
                    AgentModal(state: modalState)
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                }
                
                // Microphone button in liquid glass container - always in fixed position at bottom
                MicrophoneButtonContainer {
                    microphoneButton
                }
            }
        }
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: agentModalState != nil)
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: selectedEventForDetails != nil)
        .onReceive(viewModel.$displayState) { state in
            handleDisplayStateChange(state)
            
            // Clear EventDetailsModal when agent responses are handled (except no-action and error)
            if case .completed(let result) = state {
                switch result.agentResponse {
                case .noAction, .error:
                    // Don't clear modal for no-action or error responses
                    break
                case .showEvent, .showSchedule, .createEvent, .updateEvent, .deleteEvent:
                    // Clear modal for all action responses
                    selectedEventForDetails = nil
                }
            }
        }
        .task {
            if didConfigureViewModel == false {
                viewModel.configure(authProvider: authViewModel)
                didConfigureViewModel = true
                try? await viewModel.loadCurrentDaySchedule()
            }
        }
        .onAppear {
            // Reload schedule when view reappears (e.g., returning from Calendar Accounts page)
            // Only reload if viewModel has already been configured
            if didConfigureViewModel {
                Task {
                    try? await viewModel.loadCurrentDaySchedule(force: true)
                }
            }
        }
        .onDisappear {
            // Cleanup audio session when view disappears to free up resources
            viewModel.cleanupAudioSession()
        }
    }

    private var agentModalState: AgentModalState? {
        // Priority: error > confirmation > thinking > notice
        // Error has highest priority - critical state that needs immediate attention
        if let errorState = viewModel.errorState {
            return .error(
                message: errorState.message,
                context: errorState.context
            )
        } else if let agentAction = viewModel.agentAction, 
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
    
    private var scheduleModalPadding: CGFloat {
        // Base padding (always present) for microphone button container
        // Container height: 72pt button + 12pt top padding + 12pt bottom padding = 96pt
        let microphonePadding: CGFloat = 96 + 8 + 24 // container height (72+12+12) + gap + buffer
        
        // Additional padding when modal visible
        let modalPadding: CGFloat = agentModalState != nil ? 88 + 8 + 24 : 0 // modal height + gap + buffer
        
        return microphonePadding + modalPadding
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
        }
        .opacity(viewModel.isRecording ? 0.85 : 1.0)
        .buttonStyle(.plain)
        .disabled(isLoading)
        .onLongPressGesture(
            minimumDuration: 0,
            maximumDistance: 80,
            pressing: { pressing in
                guard !isLoading else { return }
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
    
    private func fetchFullEventDetails(event: CalendarEvent) async {
        guard let calendarId = event.calendarId,
              let accessToken = authViewModel.session?.accessToken else {
            return
        }
        
        isLoadingEventDetails = true
        defer { isLoadingEventDetails = false }
        
        do {
            let calendarService = CalendarService()
            let fullEvent = try await calendarService.fetchEvent(
                accessToken: accessToken,
                calendarId: calendarId,
                eventId: event.id
            )
            
            await MainActor.run {
                selectedEventForDetails = fullEvent
            }
        } catch {
            // If fetch fails, keep showing the event we have (even if incomplete)
            print("Failed to fetch full event details: \(error)")
        }
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
