//
//  AgentAudioRecorder.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import AVFoundation
import Combine
import Foundation

@MainActor
final class AgentAudioRecorder: NSObject, ObservableObject {
    enum RecorderState: Equatable {
        case idle
        case preparing
        case recording(startedAt: Date)
    }

    struct Recording {
        let fileURL: URL
        let duration: TimeInterval
    }

    enum RecordingError: Error {
        case permissionDenied
        case noAudioCaptured
        case failedToCreateRecorder
    }

    @Published private(set) var state: RecorderState = .idle

    private var audioRecorder: AVAudioRecorder?
    private var activeRecordingURL: URL?

    func startRecording() async throws {
        guard case .idle = state else { return }

        state = .preparing

        do {
            try await requestPermissionIfNeeded()

            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .duckOthers])
            try session.setActive(true, options: .notifyOthersOnDeactivation)

            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension("wav")

            let settings: [String: Any] = [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 16_000,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsBigEndianKey: false
            ]

            guard let recorder = try? AVAudioRecorder(url: tempURL, settings: settings) else {
                throw RecordingError.failedToCreateRecorder
            }

            recorder.isMeteringEnabled = true
            recorder.delegate = self
            recorder.prepareToRecord()
            recorder.record()

            audioRecorder = recorder
            activeRecordingURL = tempURL
            state = .recording(startedAt: Date())
        } catch {
            audioRecorder?.stop()
            audioRecorder = nil
            activeRecordingURL = nil
            state = .idle
            throw error
        }
    }

    func stopRecording() async throws -> Recording? {
        guard case let .recording(startedAt) = state else { return nil }

        audioRecorder?.stop()

        let session = AVAudioSession.sharedInstance()
        try? session.setActive(false, options: .notifyOthersOnDeactivation)

        let recordedURL = activeRecordingURL
        audioRecorder = nil
        activeRecordingURL = nil
        state = .idle

        guard let url = recordedURL else {
            throw RecordingError.noAudioCaptured
        }

        guard FileManager.default.fileExists(atPath: url.path) else {
            throw RecordingError.noAudioCaptured
        }

        let duration = Date().timeIntervalSince(startedAt)
        return Recording(fileURL: url, duration: duration)
    }
}

extension AgentAudioRecorder: AVAudioRecorderDelegate {}

extension AgentAudioRecorder {
    @MainActor
    private func requestPermissionIfNeeded() async throws {
        if #available(iOS 17.0, *) {
            let audioApp = AVAudioApplication.shared
            switch audioApp.recordPermission {
            case .granted:
                return
            case .denied:
                throw RecordingError.permissionDenied
            case .undetermined:
                let granted = await AVAudioApplication.requestRecordPermission()
                guard granted else { throw RecordingError.permissionDenied }
            @unknown default:
                throw RecordingError.permissionDenied
            }
        } else {
            let session = AVAudioSession.sharedInstance()
            switch session.recordPermission {
            case .granted:
                return
            case .denied:
                throw RecordingError.permissionDenied
            case .undetermined:
                let granted = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Bool, Error>) in
                    session.requestRecordPermission { granted in
                        continuation.resume(returning: granted)
                    }
                }
                guard granted else { throw RecordingError.permissionDenied }
            @unknown default:
                throw RecordingError.permissionDenied
            }
        }
    }
}

