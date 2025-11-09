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
    enum RecorderState {
        case idle
        case preparing
        case recording(startedAt: Date)
    }

    private let audioEngine = AVAudioEngine()
    private let mixerNode = AVAudioMixerNode()

    private var bufferData = Data()
    private var activeFormat: AVAudioFormat?
    @Published private(set) var state: RecorderState = .idle

    override init() {
        super.init()
        audioEngine.attach(mixerNode)
    }

    func startRecording() async throws {
        guard case .idle = state else { return }

        try await requestPermissionIfNeeded()

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.mixWithOthers, .defaultToSpeaker])
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        bufferData.removeAll(keepingCapacity: true)

        let inputNode = audioEngine.inputNode
        let hardwareFormat = inputNode.inputFormat(forBus: 0)

        let preferredFormat = AVAudioFormat(
            commonFormat: hardwareFormat.commonFormat,
            sampleRate: hardwareFormat.sampleRate,
            channels: 1,
            interleaved: hardwareFormat.isInterleaved
        ) ?? hardwareFormat

        audioEngine.disconnectNodeInput(mixerNode)
        audioEngine.connect(inputNode, to: mixerNode, format: preferredFormat)
        activeFormat = preferredFormat

        mixerNode.installTap(onBus: 0, bufferSize: 2048, format: preferredFormat) { [weak self] buffer, _ in
            guard let strongSelf = self else { return }
            guard let channelData = buffer.floatChannelData?.pointee else { return }

            let frameLength = Int(buffer.frameLength)
            let captured = Data(bytes: channelData, count: frameLength * MemoryLayout<Float>.size)

            Task { @MainActor in
                strongSelf.bufferData.append(captured)
            }
        }

        try audioEngine.start()
        state = .recording(startedAt: Date())
    }

    func stopRecording() async throws -> RecordedSample? {
        guard case let .recording(startedAt) = state else {
            return nil
        }

        audioEngine.stop()
        mixerNode.removeTap(onBus: 0)
        audioEngine.disconnectNodeInput(mixerNode)

        let session = AVAudioSession.sharedInstance()
        try? session.setActive(false, options: .notifyOthersOnDeactivation)

        state = .idle

        guard bufferData.isEmpty == false else {
            throw RecordingError.noAudioCaptured
        }

        let sample = RecordedSample(
            data: bufferData,
            format: activeFormat ?? audioEngine.inputNode.inputFormat(forBus: 0),
            duration: Date().timeIntervalSince(startedAt)
        )

        bufferData.removeAll(keepingCapacity: true)
        activeFormat = nil

        return sample
    }
}

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

    struct RecordedSample {
        let data: Data
        let format: AVAudioFormat
        let duration: TimeInterval
    }

    enum RecordingError: Error {
        case permissionDenied
        case noAudioCaptured
    }
}

