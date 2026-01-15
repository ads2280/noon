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
    private var hasPrewarmed = false
    private var isPermissionGranted: Bool?
    private var isSessionActive = false
    private var hasPrimedRecorder = false // Track if AVAudioRecorder infrastructure is primed

    func startRecording() async throws {
        guard case .idle = state else { return }

        state = .preparing

        do {
            // Only check permission if not already granted (skip if prewarmed and granted)
            if isPermissionGranted != true {
                try await requestPermissionIfNeeded()
            }

            let session = AVAudioSession.sharedInstance()
            
            // Skip category configuration if already prewarmed (category already set)
            if !hasPrewarmed {
                try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .duckOthers])
                
                if #available(iOS 13.0, *) {
                    try session.setAllowHapticsAndSystemSoundsDuringRecording(true)
                }
            }
            
            // Only activate session if not already active (pre-warming may have activated it)
            if !isSessionActive {
                #if targetEnvironment(simulator)
                try? session.setActive(true, options: .notifyOthersOnDeactivation)
                #else
                try session.setActive(true, options: .notifyOthersOnDeactivation)
                #endif
                isSessionActive = true
            }

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

        // Note: We don't deactivate the session here to keep it warm for next recording
        // The session will be deactivated when the view disappears or in deinit
        
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
        // Cleanup audio session on deallocation
        // Note: We can't await in deinit, so this may not complete, but we try anyway
        cleanupSession()
    }
}

extension AgentAudioRecorder: AVAudioRecorderDelegate {}

extension AgentAudioRecorder {
    /// Pre-warms the audio session by configuring category/mode, checking permissions, activating the session,
    /// and priming the AVAudioRecorder infrastructure. This eliminates initialization delay when recording starts.
    /// Safe to call multiple times.
    @MainActor
    func prewarm() {
        // Check permission status (non-blocking read)
        let session = AVAudioSession.sharedInstance()
        if #available(iOS 17.0, *) {
            let audioApp = AVAudioApplication.shared
            isPermissionGranted = audioApp.recordPermission == .granted
        } else {
            isPermissionGranted = session.recordPermission == .granted
        }
        
        // Pre-configure audio session category and mode
        do {
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .duckOthers])
            
            if #available(iOS 13.0, *) {
                try session.setAllowHapticsAndSystemSoundsDuringRecording(true)
            }
            
            hasPrewarmed = true
            
            // Activate the session asynchronously in the background
            // This is the slow part on first use, so doing it early means it's ready when user taps mic
            Task { @MainActor in
                // Only activate if not already active and permission is granted
                if !isSessionActive, isPermissionGranted == true {
                    do {
                        #if targetEnvironment(simulator)
                        try? session.setActive(true, options: .notifyOthersOnDeactivation)
                        #else
                        try session.setActive(true, options: .notifyOthersOnDeactivation)
                        #endif
                        isSessionActive = true
                        
                        // Prime AVAudioRecorder infrastructure by creating and preparing a dummy instance
                        // This initializes iOS's audio codecs and hardware pipeline, eliminating the 2+ second
                        // delay on first real recorder creation. The dummy instance is discarded after priming.
                        if !hasPrimedRecorder {
                            let dummyURL = FileManager.default.temporaryDirectory
                                .appendingPathComponent("dummy_prewarm_\(UUID().uuidString)")
                                .appendingPathExtension("wav")
                            
                            let dummySettings: [String: Any] = [
                                AVFormatIDKey: kAudioFormatLinearPCM,
                                AVSampleRateKey: 16_000,
                                AVNumberOfChannelsKey: 1,
                                AVLinearPCMBitDepthKey: 16,
                                AVLinearPCMIsFloatKey: false,
                                AVLinearPCMIsBigEndianKey: false
                            ]
                            
                            // Create and prepare the dummy recorder to prime the infrastructure
                            if let dummy = try? AVAudioRecorder(url: dummyURL, settings: dummySettings) {
                                dummy.prepareToRecord()
                                hasPrimedRecorder = true
                                // Clean up dummy file if it was created
                                try? FileManager.default.removeItem(at: dummyURL)
                            }
                        }
                    } catch {
                        // Silently fail - will retry during actual recording start
                        // This prevents pre-warming from causing issues
                    }
                }
            }
        } catch {
            // Silently fail - will retry during actual recording start
            // This prevents pre-warming from causing issues if called too early
        }
    }
    
    /// Deactivates the audio session to free up resources. Call this when the view disappears.
    @MainActor
    func cleanup() {
        guard isSessionActive else { return }
        
        let session = AVAudioSession.sharedInstance()
        #if targetEnvironment(simulator)
        try? session.setActive(false, options: .notifyOthersOnDeactivation)
        isSessionActive = false
        #else
        do {
            try session.setActive(false, options: .notifyOthersOnDeactivation)
            isSessionActive = false
        } catch {
            // Silently ignore cleanup errors
        }
        #endif
    }
    
    /// Non-isolated cleanup for use in deinit
    nonisolated private func cleanupSession() {
        Task { @MainActor in
            self.cleanup()
        }
    }
    
    @MainActor
    private func requestPermissionIfNeeded() async throws {
        let session = AVAudioSession.sharedInstance()
        
        // Check current permission status
        let currentPermission: (granted: Bool, denied: Bool)
        if #available(iOS 17.0, *) {
            let audioApp = AVAudioApplication.shared
            let status = audioApp.recordPermission
            currentPermission = (granted: status == .granted, denied: status == .denied)
        } else {
            let status = session.recordPermission
            currentPermission = (granted: status == .granted, denied: status == .denied)
        }
        
        // If already granted, update stored status and return
        if currentPermission.granted {
            isPermissionGranted = true
            return
        }
        
        // If denied, throw error
        if currentPermission.denied {
            isPermissionGranted = false
            throw RecordingError.permissionDenied
        }
        
        // If undetermined, request permission
        let granted: Bool
        if #available(iOS 17.0, *) {
            granted = await AVAudioApplication.requestRecordPermission()
        } else {
            granted = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Bool, Error>) in
                session.requestRecordPermission { granted in
                    continuation.resume(returning: granted)
                }
            }
        }
        
        // Update stored permission status
        isPermissionGranted = granted
        
        guard granted else { throw RecordingError.permissionDenied }
    }
}

