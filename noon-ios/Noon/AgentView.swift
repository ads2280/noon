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

    private let placeholderTranscript = "schedule lunch with anika at 1pm on nov 10th, monday. give it a funny title"

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
                statusLabel
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
                    viewModel.stopRecordingAndTranscribe()
                }
            },
            perform: {}
        )
        .padding(.bottom, 20)
    }

    private var statusLabel: some View {
        Group {
            if let message = errorMessage ?? statusMessage {
                Text(message)
                    .foregroundStyle(statusForegroundStyle)
                    .multilineTextAlignment(statusAlignment)
                    .font(.system(size: 16, weight: .medium))
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 32)
                    .padding(.bottom, 32)
            } else {
                Color.clear
                    .frame(height: 32)
                    .padding(.bottom, 32)
            }
        }
    }

    private var statusMessage: String? {
        switch viewModel.displayState {
        case .idle:
            return nil
        case .recording:
            return nil
        case .uploading:
            return "Transcribing…"
        case .completed, .failed:
            return nil
        }
    }

    private var statusForegroundStyle: some ShapeStyle {
        if errorMessage != nil {
            return ColorPalette.Semantic.destructive
        }

        switch viewModel.displayState {
        case .idle, .uploading:
            return ColorPalette.Text.secondary
        case .recording:
            return ColorPalette.Semantic.primary
        case .completed:
            return ColorPalette.Text.primary
        case .failed:
            return ColorPalette.Semantic.destructive
        }
    }

    private var statusAlignment: TextAlignment {
        if errorMessage != nil {
            return .leading
        }

        switch viewModel.displayState {
        case .completed, .failed:
            return .center
        default:
            return .leading
        }
    }

    private func triggerAgentQuery() async {
        await sendTranscriptToAgent(placeholderTranscript)
    }

    @MainActor
    private func sendTranscriptToAgent(_ transcript: String) async {
        guard let token = authViewModel.session?.accessToken else {
            errorMessage = "You’re signed out."
            return
        }

        isLoading = true
        errorMessage = nil

        defer { isLoading = false }

        do {
            let request = try makeAgentRequest(for: transcript, accessToken: token)
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, 200..<300 ~= httpResponse.statusCode else {
                throw URLError(.badServerResponse)
            }

            _ = try? JSONDecoder().decode(AgentResponse.self, from: data)
        } catch {
            errorMessage = "Couldn’t reach the agent. Please try again."
        }
    }

    private func makeAgentRequest(for text: String, accessToken: String) throws -> URLRequest {
        var components = URLComponents(
            url: AppConfiguration.agentBaseURL.appendingPathComponent("agent"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [
            URLQueryItem(name: "query", value: text)
        ]

        guard let url = components?.url else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        return request
    }
}

private struct AgentResponse: Decodable {
    let message: String

    init(from decoder: Decoder) throws {
        if let single = try? decoder.singleValueContainer().decode(String.self) {
            message = single
            return
        }

        let container = try decoder.container(keyedBy: CodingKeys.self)
        if let explicit = try container.decodeIfPresent(String.self, forKey: .message) {
            message = explicit
        } else if let reply = try container.decodeIfPresent(String.self, forKey: .reply) {
            message = reply
        } else if let text = try container.decodeIfPresent(String.self, forKey: .text) {
            message = text
        } else {
            message = "Agent responded."
        }
    }

    private enum CodingKeys: String, CodingKey {
        case message
        case reply
        case text
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
