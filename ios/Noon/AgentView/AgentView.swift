//
//  AgentView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import SwiftUI

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
                ScheduleView(
                    date: viewModel.scheduleDate,
                    events: viewModel.displayEvents
                )
                .padding(.horizontal, 24)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 0) {
                Color.clear
                    .frame(height: 24)

                microphoneButton
            }
        }
        .onReceive(viewModel.$displayState) { state in
            handleDisplayStateChange(state)
        }
        .task {
            if didConfigureViewModel == false {
                viewModel.configure(authProvider: authViewModel)
                didConfigureViewModel = true
            }
        }
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
                    viewModel.startRecording()
                } else if pressing == false && isPressingMic {
                    isPressingMic = false
                    viewModel.stopAndSendRecording(accessToken: authViewModel.session?.accessToken)
                }
            },
            perform: {}
        )
        .padding(.bottom, 20)
    }

    private func handleDisplayStateChange(_ state: AgentViewModel.DisplayState) {
        switch state {
        case .recording:
            isLoading = false
        case .uploading:
            isLoading = true
        case .completed:
            isLoading = false
        case .failed(let message):
            isLoading = false
            print("[Agent] Agent call failed: \(message)")
        case .idle:
            isLoading = false
        }
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
