//
//  SpeechRecognitionService.swift
//  Noon
//
//  On-device speech recognition using Apple's Speech framework.
//  Replaces the backend Deepgram transcription path for lower latency.
//

import AVFoundation
import Combine
import Foundation
import Speech

protocol SpeechRecognitionServicing: AnyObject {
    func startRecording() async throws
    func stopRecording() async throws -> String?
    var isRecording: Bool { get }
    func prewarm()
    func cleanup()
    var partialTranscriptPublisher: AnyPublisher<String, Never> { get }
}

@MainActor
final class SpeechRecognitionService: NSObject, ObservableObject, SpeechRecognitionServicing {

    enum SpeechError: Error {
        case speechPermissionDenied
        case microphonePermissionDenied
        case recognizerUnavailable
        case audioEngineError(Error)
    }

    @Published private var partialTranscript: String = ""

    var partialTranscriptPublisher: AnyPublisher<String, Never> {
        $partialTranscript.eraseToAnyPublisher()
    }

    private(set) var isRecording: Bool = false

    private var speechRecognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var audioEngine: AVAudioEngine?

    private var finalTranscript: String?
    private var finalContinuation: CheckedContinuation<String?, Never>?

    /// Guards against the recognition callback resuming the continuation after cancel/timeout
    private var continuationResumed = false

    private var hasPrewarmed = false
    private var isMicPermissionGranted: Bool?
    private var isSpeechPermissionGranted: Bool?
    private var isSessionActive = false

    override init() {
        super.init()
        let locale = Locale.current
        speechRecognizer = SFSpeechRecognizer(locale: locale) ?? SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        speechRecognizer?.delegate = self
    }

    // MARK: - Prewarm

    func prewarm() {
        // Check speech permission status (non-blocking read)
        let speechStatus = SFSpeechRecognizer.authorizationStatus()
        isSpeechPermissionGranted = speechStatus == .authorized

        // Check microphone permission status (non-blocking read)
        let session = AVAudioSession.sharedInstance()
        if #available(iOS 17.0, *) {
            isMicPermissionGranted = AVAudioApplication.shared.recordPermission == .granted
        } else {
            isMicPermissionGranted = session.recordPermission == .granted
        }

        // Pre-configure audio session
        do {
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .duckOthers])
            if #available(iOS 13.0, *) {
                try session.setAllowHapticsAndSystemSoundsDuringRecording(true)
            }
            hasPrewarmed = true

            // Activate session if permissions are granted
            Task { @MainActor in
                guard !isSessionActive,
                      isMicPermissionGranted == true,
                      isSpeechPermissionGranted == true else { return }
                do {
                    #if targetEnvironment(simulator)
                    try? session.setActive(true, options: .notifyOthersOnDeactivation)
                    #else
                    try session.setActive(true, options: .notifyOthersOnDeactivation)
                    #endif
                    isSessionActive = true
                } catch {
                    // Silently fail — will retry during actual recording start
                }
            }
        } catch {
            // Silently fail — will retry during actual recording start
        }
    }

    // MARK: - Start Recording

    func startRecording() async throws {
        guard !isRecording else { return }

        // Request permissions if needed
        try await requestPermissionsIfNeeded()

        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            throw SpeechError.recognizerUnavailable
        }

        // Configure audio session
        let session = AVAudioSession.sharedInstance()
        if !hasPrewarmed {
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .duckOthers])
            if #available(iOS 13.0, *) {
                try session.setAllowHapticsAndSystemSoundsDuringRecording(true)
            }
        }
        if !isSessionActive {
            #if targetEnvironment(simulator)
            try? session.setActive(true, options: .notifyOthersOnDeactivation)
            #else
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            #endif
            isSessionActive = true
        }

        // Create recognition request
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }

        self.recognitionRequest = request

        // Reset state
        finalTranscript = nil
        partialTranscript = ""
        continuationResumed = false

        // Start recognition task
        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor [weak self] in
                guard let self, self.isRecording || self.finalContinuation != nil else { return }

                if let result {
                    let text = result.bestTranscription.formattedString
                    if result.isFinal {
                        self.finalTranscript = text
                        self.partialTranscript = text
                        self.resumeContinuation(with: text)
                    } else {
                        self.partialTranscript = text
                    }
                }

                if let error, self.finalTranscript == nil {
                    print("Speech recognition error: \(error.localizedDescription)")
                    let fallback = self.partialTranscript.isEmpty ? nil : self.partialTranscript
                    self.resumeContinuation(with: fallback)
                }
            }
        }

        // Always create a fresh audio engine to avoid stale input node state
        let engine = AVAudioEngine()
        self.audioEngine = engine

        let inputNode = engine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        engine.prepare()
        do {
            try engine.start()
        } catch {
            inputNode.removeTap(onBus: 0)
            self.audioEngine = nil
            throw SpeechError.audioEngineError(error)
        }

        isRecording = true
    }

    // MARK: - Stop Recording

    func stopRecording() async throws -> String? {
        guard isRecording else { return nil }
        isRecording = false

        // Stop audio engine and discard it — a fresh one is created on next startRecording()
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine = nil

        // End the audio stream so the recognizer can deliver its final result
        recognitionRequest?.endAudio()
        recognitionRequest = nil

        // If we already have a final transcript, return it immediately
        if let final = finalTranscript {
            cancelRecognitionTask()
            return final
        }

        // Wait for the final result callback, with a timeout
        let transcript: String? = await withCheckedContinuation { continuation in
            self.finalContinuation = continuation
            self.continuationResumed = false

            // Timeout after 1.5 seconds — use whatever partial we have
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                let fallback = self.partialTranscript.isEmpty ? nil : self.partialTranscript
                self.resumeContinuation(with: fallback)
            }
        }

        cancelRecognitionTask()
        return transcript
    }

    // MARK: - Cleanup

    func cleanup() {
        if isRecording {
            audioEngine?.stop()
            audioEngine?.inputNode.removeTap(onBus: 0)
            recognitionRequest?.endAudio()
            isRecording = false
        }
        audioEngine = nil
        recognitionRequest = nil
        cancelRecognitionTask()

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

    // MARK: - Private

    /// Thread-safe continuation resume — ensures we only resume once
    private func resumeContinuation(with value: String?) {
        guard !continuationResumed, let continuation = finalContinuation else { return }
        continuationResumed = true
        finalContinuation = nil
        continuation.resume(returning: value)
    }

    /// Cancel (not finish) the recognition task — avoids the RPC deadlock that .finish() causes
    private func cancelRecognitionTask() {
        recognitionTask?.cancel()
        recognitionTask = nil
    }

    private func requestPermissionsIfNeeded() async throws {
        // Speech recognition permission
        if isSpeechPermissionGranted != true {
            let status = SFSpeechRecognizer.authorizationStatus()
            switch status {
            case .authorized:
                isSpeechPermissionGranted = true
            case .denied, .restricted:
                isSpeechPermissionGranted = false
                throw SpeechError.speechPermissionDenied
            case .notDetermined:
                let granted = await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
                    SFSpeechRecognizer.requestAuthorization { status in
                        continuation.resume(returning: status == .authorized)
                    }
                }
                isSpeechPermissionGranted = granted
                if !granted { throw SpeechError.speechPermissionDenied }
            @unknown default:
                throw SpeechError.speechPermissionDenied
            }
        }

        // Microphone permission
        if isMicPermissionGranted != true {
            let session = AVAudioSession.sharedInstance()
            let currentPermission: (granted: Bool, denied: Bool)
            if #available(iOS 17.0, *) {
                let status = AVAudioApplication.shared.recordPermission
                currentPermission = (granted: status == .granted, denied: status == .denied)
            } else {
                let status = session.recordPermission
                currentPermission = (granted: status == .granted, denied: status == .denied)
            }

            if currentPermission.granted {
                isMicPermissionGranted = true
            } else if currentPermission.denied {
                isMicPermissionGranted = false
                throw SpeechError.microphonePermissionDenied
            } else {
                let granted: Bool
                if #available(iOS 17.0, *) {
                    granted = await AVAudioApplication.requestRecordPermission()
                } else {
                    granted = await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
                        session.requestRecordPermission { granted in
                            continuation.resume(returning: granted)
                        }
                    }
                }
                isMicPermissionGranted = granted
                if !granted { throw SpeechError.microphonePermissionDenied }
            }
        }
    }
}

// MARK: - SFSpeechRecognizerDelegate

extension SpeechRecognitionService: SFSpeechRecognizerDelegate {
    nonisolated func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        Task { @MainActor in
            if !available && self.isRecording {
                print("Speech recognizer became unavailable during recording")
            }
        }
    }
}
