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
    @Published private(set) var focusEvent: ScheduleFocusEvent?

    // Configuration for n-day schedule
    var numberOfDays: Int = 1

    private weak var authProvider: AuthSessionProviding?
    private let recorder: AgentAudioRecorder
    private let service: AgentActionServicing
    private let scheduleService: GoogleCalendarScheduleServicing
    private let showScheduleHandler: ShowScheduleActionHandling
    private let calendar: Calendar = Calendar.autoupdatingCurrent
    
    private static let iso8601DateFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = .autoupdatingCurrent
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

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
                // print("[Agent] Uploading audio to /agent/action…")

                // MOCK: Do not call the agent action endpoint. Instead, construct a mock ShowEvent response.
                let mockResponse = AgentResponse.showEvent(
                    ShowEventResponse(
                        metadata: ShowEventMetadata(
                            eventID: "fea8bc64c5ff403e818e32864c22c8e7",
                            calendarID: "primary"
                        )
                    )
                )
                let result = AgentActionResult(statusCode: 200, data: Data(), agentResponse: mockResponse)
                let tokenUsed = startingToken

                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)

                displayState = .completed(result: result)

                // if let responseString = result.responseString {
                //     print("[Agent] Agent response (\(result.statusCode)): \(responseString)")
                // } else {
                //     print("[Agent] Agent response (\(result.statusCode)) received (\(result.data.count) bytes)")
                // }
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

    private func loadSchedule(
        for date: Date,
        force: Bool,
        accessToken initialToken: String? = nil,
        focusEvent: ScheduleFocusEvent? = nil
    ) {
        guard isLoadingSchedule == false else { return }
        if force == false, calendar.isDate(scheduleDate, inSameDayAs: date), isLoadingSchedule {
            return
        }

        Task { @MainActor in
            isLoadingSchedule = true
            defer {
                isLoadingSchedule = false
            }

            do {
                let dateRange = self.dateRange(for: date)
                
                let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
                let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
                
                let token = try await resolveAccessToken(initial: initialToken)
                let events = try await fetchScheduleEvents(
                    startDateISO: startDateISO,
                    endDateISO: endDateISO,
                    accessToken: token
                )

                scheduleDate = dateRange.start
                displayEvents = events
                self.focusEvent = focusEvent
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

    private func handle(agentResponse: AgentResponse, accessToken: String) async throws {
        switch agentResponse {
        case .showEvent(let response):
            try await handleShowEvent(response: response, accessToken: accessToken)
        default:
            // TODO: Handle additional agent response types
            break
        }
    }

    private func resolveAccessToken(initial: String?) async throws -> String {
        // Use provided token if available, otherwise get from AuthTokenProvider
        if let token = initial, !token.isEmpty {
            return token
        }
        
        // Always use AuthTokenProvider - single source of truth, always fresh (auto-refreshed by Supabase)
        guard let token = await AuthTokenProvider.shared.currentAccessToken() else {
            throw AccessTokenError.missingAuthProvider
        }
        return token
    }

    private func sendRecording(
        recording: AgentAudioRecorder.Recording,
        accessToken: String
    ) async throws -> (AgentActionResult, String) {
        // Supabase handles token refresh automatically, so we don't need manual retry logic
        // If we get 401, it means the session is truly invalid (refresh token expired, etc.)
        let result = try await service.performAgentAction(
            fileURL: recording.fileURL,
            accessToken: accessToken
        )
        return (result, accessToken)
    }

    private func fetchScheduleEvents(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> [DisplayEvent] {
        // Supabase handles token refresh automatically, so we don't need manual retry logic
        // If we get 401, it means the session is truly invalid (refresh token expired, etc.)
        let schedule = try await scheduleService.fetchSchedule(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )
        return schedule.events.map { DisplayEvent(event: $0) }
    }

    // MARK: - Show Event Handling (Mock)
    private func handleShowEvent(response: ShowEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.eventID
        let calendarID = response.metadata.calendarID
        let day = try await getDayOfEvent(eventID: eventID, calendarID: calendarID, accessToken: accessToken)
        let focus = ScheduleFocusEvent(eventID: eventID, style: .highlight)
        loadSchedule(
            for: day,
            force: true,
            accessToken: accessToken,
            focusEvent: focus
        )
    }

    private func getDayOfEvent(
        eventID: String,
        calendarID: String,
        accessToken: String
    ) async throws -> Date {
        // TODO: Replace with lookup to Google Calendar event (by id) to derive start date
        var components = DateComponents()
        components.year = 2025
        components.month = 11
        components.day = 22
        return calendar.date(from: components) ?? calendar.startOfDay(for: Date())
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
    
    // MARK: - Date Range Helpers
    
    private func dateRange(for date: Date) -> (start: Date, end: Date) {
        let normalizedDate = calendar.startOfDay(for: date)
        // End date should be the start of the day after the last day to include all events in the last day
        // For numberOfDays=2, this means: start of day 1 to start of day 3 (inclusive of all of day 2)
        let endDate = calendar.date(byAdding: .day, value: numberOfDays, to: normalizedDate) ?? normalizedDate
        return (start: normalizedDate, end: endDate)
    }

}

