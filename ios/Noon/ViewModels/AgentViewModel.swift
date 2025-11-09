//
//  AgentViewModel.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Combine
import Foundation

@MainActor
final class AgentViewModel: ObservableObject {
    enum DisplayState {
        case idle
        case recording
        case uploading
        case completed(result: AgentActionResult)
        case failed(message: String)
    }

    @Published private(set) var displayState: DisplayState = .idle
    @Published private(set) var isRecording: Bool = false

    private let recorder: AgentAudioRecorder
    private let service: AgentActionServicing

    init(
        recorder: AgentAudioRecorder? = nil,
        service: AgentActionServicing? = nil
    ) {
        self.recorder = recorder ?? AgentAudioRecorder()
        self.service = service ?? AgentActionService()
    }

    func startRecording() {
        guard isRecording == false else { return }

        isRecording = true
        displayState = .recording

        Task {
            do {
                try await recorder.startRecording()
                print("[Agent] Recording started")
            } catch {
                handle(error: error)
            }
        }
    }

    func stopAndSendRecording(accessToken: String?) {
        guard isRecording else { return }

        isRecording = false

        Task {
            do {
                print("[Agent] Stopping recording and sending to agent…")
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }

                guard let token = accessToken else {
                    try? FileManager.default.removeItem(at: recording.fileURL)
                    displayState = .failed(message: "You’re signed out.")
                    print("[Agent] Missing access token; cannot call agent.")
                    return
                }

                displayState = .uploading
                print("[Agent] Recorded audio duration: \(recording.duration)s")
                print("[Agent] Uploading audio to /agent/action…")

                let result = try await service.performAgentAction(fileURL: recording.fileURL, accessToken: token)
                displayState = .completed(result: result)

                if let responseString = result.responseString {
                    print("[Agent] Agent response (\(result.statusCode)): \(responseString)")
                } else {
                    print("[Agent] Agent response (\(result.statusCode)) received (\(result.data.count) bytes)")
                }

                try? FileManager.default.removeItem(at: recording.fileURL)
            } catch {
                handle(error: error)
            }
        }
    }

    func reset() {
        displayState = .idle
        isRecording = false
    }

    private func handle(error: Error) {
        displayState = .failed(message: localizedMessage(for: error))
        isRecording = false
        if let serverError = error as? ServerError {
            print("[Agent] Transcription failed (\(serverError.statusCode)): \(serverError.message)")
        } else {
            print("[Agent] Transcription failed: \(error.localizedDescription)")
        }
    }

    private func localizedMessage(for error: Error) -> String {
        switch error {
        case let error as AgentAudioRecorder.RecordingError:
            switch error {
            case .permissionDenied:
                return "Microphone access denied. Enable in Settings."
            case .noAudioCaptured:
                return "No audio captured. Try again."
            case .failedToCreateRecorder:
                return "Could not start microphone."
            }
        case let error as ServerError:
            return "Transcription failed (\(error.statusCode)): \(error.message)"
        default:
            return "Something went wrong: \(error.localizedDescription)"
        }
    }
}

