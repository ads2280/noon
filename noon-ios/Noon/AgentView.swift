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
        guard let token = authViewModel.session?.accessToken else {
            errorMessage = "You’re signed out."
            return
        }

        let trimmedTranscript = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedTranscript.isEmpty == false else { return }

        isLoading = true
        errorMessage = nil
        agentMessage = nil

        defer { isLoading = false }

        do {
            let request = try makeAgentRequest(for: trimmedTranscript, accessToken: token)
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }

            let statusCode = httpResponse.statusCode
            if 200..<300 ~= statusCode {
                let agentResponse = try AgentResponse.decode(from: data)
                agentMessage = agentResponse.summary
                print("[Agent] Agent response: \(agentResponse.summary)")
                if let debug = agentResponse.debugDescription {
                    print("[Agent] Response details: \(debug)")
                }
            } else {
                let detail = AgentResponse.errorMessage(from: data)
                let statusDescription = HTTPURLResponse.localizedString(forStatusCode: statusCode)
                var logMessage = "[Agent] Agent request failed (\(statusCode) \(statusDescription))"
                if let detail, detail.isEmpty == false {
                    logMessage.append(": \(detail)")
                }
                if let rawBody = String(data: data, encoding: .utf8), rawBody.isEmpty == false {
                    logMessage.append(" | body=\(rawBody)")
                }
                print(logMessage)
            }
        } catch {
            errorMessage = nil
            print("[Agent] Agent request failed: \(error.localizedDescription)")
        }
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

private struct AgentRequest: Encodable {
    let text: String
}

private struct AgentResponse {
    let summary: String
    let debugDescription: String?

    static func decode(from data: Data) throws -> AgentResponse {
        if let jsonObject = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] {
            let summary = (jsonObject["summary"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
            let tool = jsonObject["tool"] as? String
            let success = jsonObject["success"]
            let result = jsonObject["result"]

            let details = AgentResponse.stringify(tool: tool, success: success, result: result)
            return AgentResponse(
                summary: summary?.isEmpty == false ? summary! : "Agent responded.",
                debugDescription: details
            )
        }

        if let summaryString = String(data: data, encoding: .utf8) {
            return AgentResponse(summary: summaryString, debugDescription: nil)
        }

        return AgentResponse(summary: "Agent responded.", debugDescription: nil)
    }

    private static func stringify(tool: Any?, success: Any?, result: Any?) -> String? {
        var parts: [String] = []
        if let tool = tool {
            parts.append("tool=\(tool)")
        }
        if let success = success {
            parts.append("success=\(success)")
        }
        if let result = result {
            if let json = AgentResponse.normalizedJSONObject(result),
               let data = try? JSONSerialization.data(withJSONObject: json, options: [.sortedKeys]),
               let string = String(data: data, encoding: .utf8) {
                parts.append("result=\(string)")
            } else {
                parts.append("result=\(result)")
            }
        }
        guard parts.isEmpty == false else { return nil }
        return parts.joined(separator: " ")
    }

    private static func normalizedJSONObject(_ value: Any) -> Any? {
        if let dict = value as? [String: Any], JSONSerialization.isValidJSONObject(dict) {
            return dict
        }
        if let array = value as? [Any], JSONSerialization.isValidJSONObject(array) {
            return array
        }
        return nil
    }

    static func errorMessage(from data: Data) -> String? {
        if let jsonObject = try? JSONSerialization.jsonObject(with: data, options: []) {
            if let dictionary = jsonObject as? [String: Any] {
                if let detail = dictionary["detail"] {
                    return AgentResponse.coerceToString(detail)
                }
                if let message = dictionary["message"] {
                    return AgentResponse.coerceToString(message)
                }
                if let error = dictionary["error"] {
                    return AgentResponse.coerceToString(error)
                }
            } else if let array = jsonObject as? [Any], let first = array.first {
                return AgentResponse.coerceToString(first)
            }
        }

        if let string = String(data: data, encoding: .utf8), string.isEmpty == false {
            return string
        }

        return nil
    }

    private static func coerceToString(_ value: Any) -> String? {
        if let string = value as? String {
            return string
        }
        if let convertible = value as? CustomStringConvertible {
            return convertible.description
        }
        if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
           let string = String(data: data, encoding: .utf8) {
            return string
        }
        return nil
    }
}

#Preview {
    AgentView()
        .environmentObject(AuthViewModel())
}
