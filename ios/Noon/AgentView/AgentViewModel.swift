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
    @Published private(set) var scheduleDate: Date
    @Published private(set) var displayEvents: [DisplayEvent]
    @Published private(set) var isLoadingSchedule: Bool = false
    @Published private(set) var hasLoadedSchedule: Bool = false

    private weak var authProvider: AuthSessionProviding?
    private let recorder: AgentAudioRecorder
    private let service: AgentActionServicing
    private let scheduleService: GoogleCalendarScheduleServicing
    private let showScheduleHandler: ShowScheduleActionHandling
    private let calendar: Calendar = Calendar.autoupdatingCurrent
    private var isFetchingSchedule: Bool = false

    init(
        recorder: AgentAudioRecorder? = nil,
        service: AgentActionServicing? = nil,
        scheduleService: GoogleCalendarScheduleServicing? = nil,
        showScheduleHandler: ShowScheduleActionHandling? = nil,
        initialScheduleDate: Date = Date(),
        initialDisplayEvents: [DisplayEvent]? = nil
    ) {
        self.recorder = recorder ?? AgentAudioRecorder()
        self.service = service ?? AgentActionService()
        self.scheduleService = scheduleService ?? GoogleCalendarScheduleService()
        self.showScheduleHandler = showScheduleHandler ?? ShowScheduleActionHandler()
        self.scheduleDate = calendar.startOfDay(for: initialScheduleDate)
        self.displayEvents = initialDisplayEvents ?? []
        self.hasLoadedSchedule = !(initialDisplayEvents?.isEmpty ?? true)
    }

    func configure(authProvider: AuthSessionProviding) {
        self.authProvider = authProvider
    }

    func startRecording() {
        guard isRecording == false else { return }

        isRecording = true
        displayState = .recording

        Task { @MainActor in
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

        Task { @MainActor in
            do {
                print("[Agent] Stopping recording and sending to agent…")
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }
                defer { try? FileManager.default.removeItem(at: recording.fileURL) }

                let startingToken = try await resolveAccessToken(initial: accessToken)

                displayState = .uploading
                print("[Agent] Recorded audio duration: \(recording.duration)s")
                print("[Agent] Uploading audio to /agent/action…")

                let (result, tokenUsed) = try await sendRecording(
                    recording: recording,
                    accessToken: startingToken,
                    allowRetry: true
                )

                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)

                displayState = .completed(result: result)

                if let responseString = result.responseString {
                    print("[Agent] Agent response (\(result.statusCode)): \(responseString)")
                } else {
                    print("[Agent] Agent response (\(result.statusCode)) received (\(result.data.count) bytes)")
                }
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

    func loadCurrentDaySchedule(force: Bool = false) {
        let today = Date()
        loadSchedule(for: today, force: force)
    }

    private func loadSchedule(for date: Date, force: Bool) {
        guard isFetchingSchedule == false else { return }
        if force == false, calendar.isDate(scheduleDate, inSameDayAs: date), isLoadingSchedule {
            return
        }

        isFetchingSchedule = true

        Task { @MainActor in
            isLoadingSchedule = true
            defer {
                isLoadingSchedule = false
                isFetchingSchedule = false
            }

            do {
                let normalizedDate = calendar.startOfDay(for: date)
                let endDate = calendar.date(byAdding: .day, value: 1, to: normalizedDate) ?? normalizedDate
                
                let timezone = TimeZone.autoupdatingCurrent
                let formatter = ISO8601DateFormatter()
                formatter.timeZone = timezone
                formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                
                let startDateISO = formatter.string(from: normalizedDate)
                let endDateISO = formatter.string(from: endDate)
                
                let accessToken = try await resolveAccessToken(initial: nil)
                let events = try await fetchScheduleEvents(
                    startDateISO: startDateISO,
                    endDateISO: endDateISO,
                    accessToken: accessToken,
                    allowRetry: true
                )

                scheduleDate = normalizedDate
                displayEvents = events
                hasLoadedSchedule = true
            } catch {
                handle(error: error)
            }
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
        case let error as GoogleCalendarScheduleServiceError:
            return error.localizedDescription
        case let error as AccessTokenError:
            return error.userFacingMessage
        default:
            return "Something went wrong: \(error.localizedDescription)"
        }
    }

    private func handle(agentResponse _: AgentResponse, accessToken: String) async throws {
        isLoadingSchedule = true
        defer { isLoadingSchedule = false }

        let result = try await showScheduleHandler.fetchTodaySchedule(accessToken: accessToken)
        scheduleDate = result.startDate
        displayEvents = result.displayEvents
        hasLoadedSchedule = true
    }

    private func resolveAccessToken(initial: String?) async throws -> String {
        if let token = initial, token.isEmpty == false {
            return token
        }

        if let provider = authProvider, let session = provider.session {
            if session.accessToken.isEmpty == false {
                return session.accessToken
            }
        }

        return try await refreshAccessToken()
    }

    private func refreshAccessToken() async throws -> String {
        guard let provider = authProvider else {
            throw AccessTokenError.missingAuthProvider
        }

        let stored = try await provider.refreshSession()
        return stored.session.accessToken
    }

    private func sendRecording(
        recording: AgentAudioRecorder.Recording,
        accessToken: String,
        allowRetry: Bool
    ) async throws -> (AgentActionResult, String) {
        do {
            let result = try await service.performAgentAction(
                fileURL: recording.fileURL,
                accessToken: accessToken
            )
            return (result, accessToken)
        } catch let serverError as ServerError where serverError.statusCode == 401 && allowRetry {
            let refreshedToken = try await refreshAccessToken()
            let retryResult = try await service.performAgentAction(
                fileURL: recording.fileURL,
                accessToken: refreshedToken
            )
            return (retryResult, refreshedToken)
        } catch {
            throw error
        }
    }

    private func fetchScheduleEvents(
        startDateISO: String,
        endDateISO: String,
        accessToken: String,
        allowRetry: Bool
    ) async throws -> [DisplayEvent] {
        do {
            let schedule = try await scheduleService.fetchSchedule(
                startDateISO: startDateISO,
                endDateISO: endDateISO,
                accessToken: accessToken
            )
            return schedule.events.map { DisplayEvent(event: $0) }
        } catch let serviceError as GoogleCalendarScheduleServiceError {
            if case .unauthorized = serviceError, allowRetry {
                let refreshedToken = try await refreshAccessToken()
                let schedule = try await scheduleService.fetchSchedule(
                    startDateISO: startDateISO,
                    endDateISO: endDateISO,
                    accessToken: refreshedToken
                )
                return schedule.events.map { DisplayEvent(event: $0) }
            }
            throw serviceError
        } catch {
            throw error
        }
    }

    private enum AccessTokenError: Error {
        case missingAuthProvider

        var userFacingMessage: String {
            switch self {
            case .missingAuthProvider:
                return "We couldn't access your account. Please sign in again."
            }
        }
    }
}

