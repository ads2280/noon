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
                print("Recording started")
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
                print("Stopping recording and sending to agent…")
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }
                defer { try? FileManager.default.removeItem(at: recording.fileURL) }

                let startingToken = try await resolveAccessToken(initial: accessToken)

                displayState = .uploading
                print("Recorded audio duration: \(recording.duration)s")
                print("Uploading audio to /agent/action…")

                let (result, tokenUsed) = try await sendRecording(
                    recording: recording,
                    accessToken: startingToken
                )

                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)

                displayState = .completed(result: result)

                if let responseString = result.responseString {
                    print("Agent response (\(result.statusCode)): \(responseString)")
                } else {
                    print("Agent response (\(result.statusCode)) received (\(result.data.count) bytes)")
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
            print("Transcription failed (\(serverError.statusCode)): \(serverError.message)")
        } else {
            print("Transcription failed: \(error.localizedDescription)")
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
        guard isLoadingSchedule == false else {
            print("loadSchedule: Already loading, skipping")
            return
        }
        if force == false, calendar.isDate(scheduleDate, inSameDayAs: date), isLoadingSchedule {
            print("loadSchedule: Same date and not forced, skipping")
            return
        }

        let dateString = Self.iso8601DateFormatter.string(from: date)
        print("loadSchedule: Loading schedule for date: \(dateString), force: \(force)")

        Task { @MainActor in
            isLoadingSchedule = true
            defer {
                isLoadingSchedule = false
            }

            do {
                let dateRange = self.dateRange(for: date)
                
                let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
                let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
                
                print("loadSchedule: Fetching events from \(startDateISO) to \(endDateISO)")
                
                let token = try await resolveAccessToken(initial: initialToken)
                let events = try await fetchScheduleEvents(
                    startDateISO: startDateISO,
                    endDateISO: endDateISO,
                    accessToken: token
                )

                print("loadSchedule: Loaded \(events.count) events")
                scheduleDate = dateRange.start
                displayEvents = events
                self.focusEvent = focusEvent
                hasLoadedSchedule = true
                print("loadSchedule: hasLoadedSchedule set to true, scheduleDate: \(Self.iso8601DateFormatter.string(from: scheduleDate)), displayEvents count: \(displayEvents.count), focusEvent: \(focusEvent?.eventID ?? "nil")")
            } catch {
                print("loadSchedule: Error loading schedule: \(error)")
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
        case .showSchedule:
            try await handleShowSchedule(agentResponse: agentResponse, accessToken: accessToken)
        case .deleteEvent(let response):
            try await handleDeleteEvent(response: response, accessToken: accessToken)
        case .updateEvent(let response):
            try await handleUpdateEvent(response: response, accessToken: accessToken)
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
        // Try the request first
        let request = AgentActionRequest(fileURL: recording.fileURL)
        
        do {
            let result = try await service.performAgentAction(
                request: request,
                accessToken: accessToken
            )
            return (result, accessToken)
        } catch let error as ServerError where error.statusCode == 401 {
            // Token expired - refresh and retry once
            print("Got 401, refreshing token and retrying...")
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            let result = try await service.performAgentAction(
                request: request,
                accessToken: refreshedToken
            )
            return (result, refreshedToken)
        }
    }

    private func fetchScheduleEvents(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> [DisplayEvent] {
        // Try the request first
        do {
            let schedule = try await scheduleService.fetchSchedule(
                startDateISO: startDateISO,
                endDateISO: endDateISO,
                accessToken: accessToken
            )
            return schedule.events.map { DisplayEvent(event: $0) }
        } catch GoogleCalendarScheduleServiceError.unauthorized {
            // Token expired - refresh and retry once
            print("Got 401 fetching schedule, refreshing token and retrying...")
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            let schedule = try await scheduleService.fetchSchedule(
                startDateISO: startDateISO,
                endDateISO: endDateISO,
                accessToken: refreshedToken
            )
            return schedule.events.map { DisplayEvent(event: $0) }
        }
    }

    // MARK: - Show Event Handling
    private func handleShowEvent(response: ShowEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        let schedule = try await scheduleService.fetchEventSurroundingSchedule(
            eventID: eventID,
            calendarID: calendarID,
            timezone: timezone,
            accessToken: accessToken
        )
        
        // Find the event in the schedule to get its start date
        guard let targetEvent = schedule.events.first(where: { $0.id == eventID }),
              let eventStartDate = targetEvent.start?.dateTime else {
            print("ERROR: Could not find event \(eventID) in schedule or event has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event not found in schedule"])
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)
        let dateString = Self.iso8601DateFormatter.string(from: eventDay)
        print("Show event called for event: \(eventID), day: \(dateString)")
        
        // Use the events from the surrounding schedule directly
        let displayEvents = schedule.events.map { DisplayEvent(event: $0) }
        let focus = ScheduleFocusEvent(eventID: eventID, style: .highlight)
        
        // Update the schedule state directly
        let dateRange = self.dateRange(for: eventDay)
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        print("Show event: Set schedule with \(displayEvents.count) events, scheduleDate: \(Self.iso8601DateFormatter.string(from: scheduleDate)), hasLoadedSchedule: \(hasLoadedSchedule)")
    }

    // MARK: - Delete Event Handling
    private func handleDeleteEvent(response: DeleteEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        let schedule = try await scheduleService.fetchEventSurroundingSchedule(
            eventID: eventID,
            calendarID: calendarID,
            timezone: timezone,
            accessToken: accessToken
        )
        
        // Find the event in the schedule to get its start date
        guard let targetEvent = schedule.events.first(where: { $0.id == eventID }),
              let eventStartDate = targetEvent.start?.dateTime else {
            print("ERROR: Could not find event \(eventID) in schedule or event has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event not found in schedule"])
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)
        let dateString = Self.iso8601DateFormatter.string(from: eventDay)
        print("Delete event called for event: \(eventID), day: \(dateString)")
        
        // Use the events from the surrounding schedule directly
        let displayEvents = schedule.events.map { DisplayEvent(event: $0) }
        let focus = ScheduleFocusEvent(eventID: eventID, style: .destructive)
        
        // Update the schedule state directly
        let dateRange = self.dateRange(for: eventDay)
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        print("Delete event: Set schedule with \(displayEvents.count) events, scheduleDate: \(Self.iso8601DateFormatter.string(from: scheduleDate)), hasLoadedSchedule: \(hasLoadedSchedule)")
    }

    // MARK: - Update Event Handling
    private func handleUpdateEvent(response: UpdateEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        let schedule = try await scheduleService.fetchEventSurroundingSchedule(
            eventID: eventID,
            calendarID: calendarID,
            timezone: timezone,
            accessToken: accessToken
        )
        
        // Find the event in the schedule to get its start date
        guard let targetEvent = schedule.events.first(where: { $0.id == eventID }),
              let eventStartDate = targetEvent.start?.dateTime else {
            print("ERROR: Could not find event \(eventID) in schedule or event has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event not found in schedule"])
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)
        let dateString = Self.iso8601DateFormatter.string(from: eventDay)
        print("Update event called for event: \(eventID), day: \(dateString)")
        
        // Use the events from the surrounding schedule directly
        let displayEvents = schedule.events.map { DisplayEvent(event: $0) }
        let focus = ScheduleFocusEvent(eventID: eventID, style: .update)
        
        // Update the schedule state directly
        let dateRange = self.dateRange(for: eventDay)
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        print("Update event: Set schedule with \(displayEvents.count) events, scheduleDate: \(Self.iso8601DateFormatter.string(from: scheduleDate)), hasLoadedSchedule: \(hasLoadedSchedule)")
    }

    // MARK: - Show Schedule Handling
    private func handleShowSchedule(agentResponse: AgentResponse, accessToken: String) async throws {
        let config = showScheduleHandler.configuration(for: agentResponse)
        let dateString = Self.iso8601DateFormatter.string(from: config.date)
        print("Show schedule called for day: \(dateString)")
        loadSchedule(
            for: config.date,
            force: true,
            accessToken: accessToken,
            focusEvent: config.focusEvent
        )
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

