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
            // Set category before activating to reduce configuration warnings
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .duckOthers])
            
            // Allow haptics and system sounds during recording (iOS 13.0+)
            if #available(iOS 13.0, *) {
                try session.setAllowHapticsAndSystemSoundsDuringRecording(true)
            }
            
            // Handle activation gracefully to reduce HAL warnings in Simulator
            #if targetEnvironment(simulator)
            // In Simulator, use try? to suppress harmless audio device warnings
            try? session.setActive(true, options: .notifyOthersOnDeactivation)
            #else
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            #endif

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

        // Stop recorder first before deactivating session to reduce "reconfig pending" warnings
        audioRecorder?.stop()
        
        // Small delay to allow audio system to process the stop before session deactivation
        // This reduces "Abandoning I/O cycle because reconfig pending" warnings
        try? await Task.sleep(nanoseconds: 50_000_000) // 50ms delay

        let session = AVAudioSession.sharedInstance()
        // Gracefully deactivate audio session to reduce HAL warnings
        // Use try? to suppress warnings in Simulator where audio device may not be available
        #if targetEnvironment(simulator)
        // In Simulator, audio device errors are expected and harmless
        try? session.setActive(false, options: .notifyOthersOnDeactivation)
        #else
        do {
            try session.setActive(false, options: .notifyOthersOnDeactivation)
        } catch {
            // Log but don't fail if deactivation fails (common in Simulator)
            // This reduces verbose HAL error messages
        }
        #endif

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
    
    deinit {
        // Cleanup audio session on deallocation to reduce warnings
        #if targetEnvironment(simulator)
        // In Simulator, suppress cleanup errors
        try? AVAudioSession.sharedInstance().setActive(false)
        #else
        do {
            try AVAudioSession.sharedInstance().setActive(false)
        } catch {
            // Silently ignore cleanup errors
        }
        #endif
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

