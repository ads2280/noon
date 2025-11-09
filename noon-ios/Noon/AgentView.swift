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
    @State private var errorMessage: String?
    @State private var agentMessage: String?
    @State private var agentTask: Task<Void, Never>?

    var body: some View {
        ZStack {
            ColorPalette.Gradients.backgroundBase
                .ignoresSafeArea()

            VStack(spacing: 24) {
                ScheduleView(date: Date())
                    .padding(.horizontal, 24)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)

                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
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
                    viewModel.stopRecordingAndTranscribe()
                }
            },
            perform: {}
        )
        .padding(.bottom, 20)
    }

    private func handleDisplayStateChange(_ state: AgentViewModel.DisplayState) {
        switch state {
        case .recording, .uploading:
            agentTask?.cancel()
            agentTask = nil
            agentMessage = nil
            errorMessage = nil
            isLoading = false
        case .completed(let transcript):
            guard transcript.isEmpty == false else { return }
            agentTask?.cancel()
            agentTask = Task { @MainActor in
                await sendTranscriptToAgent(transcript)
                agentTask = nil
            }
        case .failed(let message):
            agentTask?.cancel()
            agentTask = nil
            agentMessage = nil
            errorMessage = message
            isLoading = false
        case .idle:
            break
        }
    }

    @MainActor
    private func sendTranscriptToAgent(_ transcript: String) async {
        let sanitized = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard sanitized.isEmpty == false else {
            print("[Agent] Dummy handler received an empty transcript. Resetting state.")
            viewModel.reset()
            return
        }

        isLoading = true
        errorMessage = nil
        defer {
            isLoading = false
            viewModel.reset()
        }

        do {
            # TODO: Replace with actual agent request
            try await Task.sleep(nanoseconds: 300_000_000)
        } catch is CancellationError {
            print("[Agent] Dummy handler cancelled before completion.")
            return
        } catch {
            print("[Agent] Unexpected error in dummy handler: \(error.localizedDescription)")
            return
        }

        agentMessage = "Dummy agent received transcript: \"\(sanitized)\""
        print("[Agent] Dummy handler processed transcript: \(sanitized)")
    }

    private func makeAgentRequest(for text: String, accessToken: String) throws -> URLRequest {
        let baseURL = AppConfiguration.agentBaseURL
        let agentURL = baseURL.appendingPathComponent("agent/chat")

        var request = URLRequest(url: agentURL)
        request.httpMethod = "POST"
        request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        let payload = AgentRequest(text: text)
        request.httpBody = try JSONEncoder().encode(payload)
        return request
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
