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
        case completed(text: String)
        case failed(message: String)
    }

    @Published private(set) var displayState: DisplayState = .idle
    @Published private(set) var isRecording: Bool = false

    private let recorder: AgentAudioRecorder
    private let service: TranscriptionServicing

    init(
        recorder: AgentAudioRecorder? = nil,
        service: TranscriptionServicing? = nil
    ) {
        self.recorder = recorder ?? AgentAudioRecorder()
        self.service = service ?? TranscriptionService()
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

    func stopRecordingAndTranscribe() {
        guard isRecording else { return }

        isRecording = false

        Task {
            do {
                print("[Agent] Stopping recording and requesting transcript…")
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }

                displayState = .uploading
                print("[Agent] Recorded audio duration: \(recording.duration)s")
                print("[Agent] Uploading audio to transcription service…")

                let result = try await service.transcribeAudio(at: recording.fileURL)
                displayState = .completed(text: result.text)
                print("[Agent] Transcription response (\(result.statusCode)): \(result.text)")

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

