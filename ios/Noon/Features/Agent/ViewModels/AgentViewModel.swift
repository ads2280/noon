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
    @Published var pendingAction: PendingAction?
    @Published var isConfirmingAction: Bool = false
    
    enum PendingAction {
        case createEvent(CreateEventResponse)
        case deleteEvent(DeleteEventResponse)
        case updateEvent(UpdateEventResponse)
    }

    // Configuration for n-day schedule
    var numberOfDays: Int = 2

    private weak var authProvider: AuthSessionProviding?
    private let recorder: AgentAudioRecorder
    private let service: AgentActionServicing
    private let transcriptionService: TranscriptionServicing
    private let scheduleService: GoogleCalendarScheduleServicing
    private let calendarService: CalendarServicing
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
        transcriptionService: TranscriptionServicing? = nil,
        scheduleService: GoogleCalendarScheduleServicing? = nil,
        calendarService: CalendarServicing? = nil,
        showScheduleHandler: ShowScheduleActionHandling? = nil,
        initialScheduleDate: Date = Date(),
        initialDisplayEvents: [DisplayEvent]? = nil
    ) {
        self.recorder = recorder ?? AgentAudioRecorder()
        self.service = service ?? AgentActionService()
        self.transcriptionService = transcriptionService ?? TranscriptionService()
        self.scheduleService = scheduleService ?? GoogleCalendarScheduleService()
        self.calendarService = calendarService ?? CalendarService()
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
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }
                defer { try? FileManager.default.removeItem(at: recording.fileURL) }

                let startingToken = try await resolveAccessToken(initial: accessToken)

                displayState = .uploading
                
                // Step 1: Transcribe audio
                let transcriptionResult = try await transcribeAudio(
                    recording: recording,
                    accessToken: startingToken
                )
                let transcribedText = transcriptionResult.text
                print("Transcribed: \"\(transcribedText)\"")
                
                // Step 2: Send to agent
                let (result, tokenUsed) = try await sendToAgent(
                    query: transcribedText,
                    accessToken: startingToken
                )

                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)

                displayState = .completed(result: result)

                if let responseString = result.responseString {
                    print("Agent response (\(result.statusCode)): \(responseString)")
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
            print("Request failed (\(serverError.statusCode)): \(serverError.message)")
        } else {
            print("Request failed: \(error.localizedDescription)")
        }
    }

    func loadCurrentDaySchedule(force: Bool = false) {
        let today = Date()
        loadSchedule(for: today, force: force)
    }

    /// Load schedule for a given date using the unified `/api/v1/calendars/schedule` endpoint.
    /// 
    /// This method is used by all agent-driven schedule displays:
    /// - show-schedule: Uses the date from agent metadata
    /// - show-event: Fetches event to get start date, then loads schedule
    /// - update-event: Uses metadata start date or fetches event, then loads schedule
    /// - delete-event: Fetches event to get start date, then loads schedule
    /// - create-event: Uses metadata start date, then loads schedule
    ///
    /// All flows use the same n-day window logic via `dateRange(for:)` and fetch events
    /// from the unified schedule endpoint.
    private func loadSchedule(
        for date: Date,
        force: Bool,
        accessToken initialToken: String? = nil,
        focusEvent: ScheduleFocusEvent? = nil
    ) {
        guard isLoadingSchedule == false else {
            return
        }
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

                print("Loaded schedule: \(events.count) events")
                scheduleDate = dateRange.start
                displayEvents = events
                self.focusEvent = focusEvent
                hasLoadedSchedule = true
            } catch {
                print("Error loading schedule: \(error)")
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
            return "Request failed (\(error.statusCode)): \(error.message)"
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
        case .createEvent(let response):
            try await handleCreateEvent(response: response, accessToken: accessToken)
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

    private func transcribeAudio(
        recording: AgentAudioRecorder.Recording,
        accessToken: String
    ) async throws -> TranscriptionResult {
        let request = TranscriptionRequest(fileURL: recording.fileURL)
        
        do {
            return try await transcriptionService.transcribe(
                request: request,
                accessToken: accessToken
            )
        } catch let error as ServerError where error.statusCode == 401 {
            // Token expired - refresh and retry once
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            return try await transcriptionService.transcribe(
                request: request,
                accessToken: refreshedToken
            )
        }
    }
    
    private func sendToAgent(
        query: String,
        accessToken: String
    ) async throws -> (AgentActionResult, String) {
        let request = AgentActionRequest(query: query)
        
        do {
            let result = try await service.performAgentAction(
                request: request,
                accessToken: accessToken
            )
            return (result, accessToken)
        } catch let error as ServerError where error.statusCode == 401 {
            // Token expired - refresh and retry once
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
        
        // Fetch the event to get its start date
        let event = try await calendarService.fetchEvent(
            accessToken: accessToken,
            calendarId: calendarID,
            eventId: eventID
        )
        
        guard let eventStartDate = event.start?.dateTime else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)

        // Load schedule for the event's day with highlight focus
        loadSchedule(
            for: eventDay,
            force: true,
            accessToken: accessToken,
            focusEvent: ScheduleFocusEvent(eventID: eventID, style: .highlight)
        )
    }

    // MARK: - Delete Event Handling
    private func handleDeleteEvent(response: DeleteEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        
        // Fetch the event to get its start date
        let event = try await calendarService.fetchEvent(
            accessToken: accessToken,
            calendarId: calendarID,
            eventId: eventID
        )
        
        guard let eventStartDate = event.start?.dateTime else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)

        // Store the pending delete event response for confirmation
        self.pendingAction = .deleteEvent(response)
        
        // Load schedule for the event's day with destructive focus
        loadSchedule(
            for: eventDay,
            force: true,
            accessToken: accessToken,
            focusEvent: ScheduleFocusEvent(eventID: eventID, style: .destructive)
        )
    }

    // MARK: - Update Event Handling
    private func handleUpdateEvent(response: UpdateEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        
        // Try to get start date from metadata first, otherwise fetch the event
        let eventStartDate: Date
        if let metadataStart = response.metadata.start?.dateTime {
            eventStartDate = metadataStart
        } else {
            // Fetch the event to get its start date
            let event = try await calendarService.fetchEvent(
                accessToken: accessToken,
                calendarId: calendarID,
                eventId: eventID
            )
            guard let startDate = event.start?.dateTime else {
                print("ERROR: Event \(eventID) has no start date")
                throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
            }
            eventStartDate = startDate
        }
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: eventStartDate)

        // Load schedule for the event's day with update focus
        loadSchedule(
            for: eventDay,
            force: true,
            accessToken: accessToken,
            focusEvent: ScheduleFocusEvent(eventID: eventID, style: .update)
        )

        // Store the pending update event response for confirmation
        self.pendingAction = .updateEvent(response)
    }

    // MARK: - Create Event Handling
    private func handleCreateEvent(response: CreateEventResponse, accessToken: String) async throws {
        let metadata = response.metadata
        let startDate = metadata.start.dateTime
        let endDate = metadata.end.dateTime
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        // Use the day of the event's start date
        let eventDay = calendar.startOfDay(for: startDate)

        // Fetch the schedule for that day
        let dateRange = self.dateRange(for: eventDay)
        let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
        let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
        
        var displayEvents = try await fetchScheduleEvents(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )
        
        // Create a temporary CalendarEvent from the metadata
        let tempEventID = UUID().uuidString
        let startEventDateTime = CalendarEvent.EventDateTime(
            dateTime: startDate,
            date: nil,
            timeZone: timezone
        )
        let endEventDateTime = CalendarEvent.EventDateTime(
            dateTime: endDate,
            date: nil,
            timeZone: timezone
        )
        
        let tempEvent = CalendarEvent(
            id: tempEventID,
            title: metadata.summary,
            description: metadata.description,
            start: startEventDateTime,
            end: endEventDateTime,
            attendees: [],
            createdBy: nil,
            calendarId: metadata.calendar_id,
            location: metadata.location,
            conference: nil
        )
        
        // Add the temporary event to the display events with .new style
        let newDisplayEvent = DisplayEvent(event: tempEvent, style: .new)
        displayEvents.append(newDisplayEvent)
        
        // Sort events by start time
        displayEvents.sort { event1, event2 in
            guard let start1 = event1.event.start?.dateTime,
                  let start2 = event2.event.start?.dateTime else {
                return false
            }
            return start1 < start2
        }
        
        // Set focus event with .new style
        let focus = ScheduleFocusEvent(eventID: tempEventID, style: .new)
        
        // Update the schedule state directly
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        // Store the pending create event response for confirmation
        self.pendingAction = .createEvent(response)
    }

    // MARK: - Event Confirmation
    func confirmPendingAction(accessToken: String?) async {
        guard let action = pendingAction else {
            return
        }
        
        // Clear pending action immediately so modal disappears
        pendingAction = nil
        
        isConfirmingAction = true
        defer { isConfirmingAction = false }
        
        switch action {
        case .createEvent(let response):
            await confirmCreateEvent(response: response, accessToken: accessToken)
        case .deleteEvent(let response):
            await confirmDeleteEvent(response: response, accessToken: accessToken)
        case .updateEvent(let response):
            await confirmUpdateEvent(response: response, accessToken: accessToken)
        }
    }
    
    func cancelPendingAction() {
        guard let action = pendingAction else { return }
        
        switch action {
        case .createEvent:
            // Remove the temporary event from display events
            if let tempEventID = focusEvent?.eventID,
               let tempEventIndex = displayEvents.firstIndex(where: { $0.event.id == tempEventID }) {
                displayEvents.remove(at: tempEventIndex)
                focusEvent = nil
            }
        case .deleteEvent:
            // Clear the focus event to remove destructive style
            focusEvent = nil
        case .updateEvent:
            // Clear the focus event to remove update style
            focusEvent = nil
        }
        
        // Clear pending action
        pendingAction = nil
    }
    
    private func confirmCreateEvent(response: CreateEventResponse, accessToken: String?) async {
        let metadata = response.metadata
        let startDate = metadata.start.dateTime
        let endDate = metadata.end.dateTime
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        Task { @MainActor in
            do {
                let token = try await resolveAccessToken(initial: accessToken)
                
                // Create the event creation request
                let createRequest = CreateEventRequest(
                    summary: metadata.summary,
                    start: startDate,
                    end: endDate,
                    calendarId: metadata.calendar_id,
                    description: metadata.description,
                    location: metadata.location,
                    timezone: timezone
                )
                
                // Call the calendar service to create the event
                let createdResponse = try await calendarService.createEvent(
                    accessToken: token,
                    request: createRequest
                )
                
                // Reload the schedule to get the real event from Google Calendar
                // This ensures the event displays properly without the .new style
                let createdEvent = createdResponse.event
                let createdEventID = createdEvent.id
                let eventDay = calendar.startOfDay(for: startDate)
                
                // Reload schedule for the day of the created event
                // No focus event - display normally without special styling
                loadSchedule(
                    for: eventDay,
                    force: true,
                    accessToken: token,
                    focusEvent: nil
                )
                
                print("Created event: \(createdEventID)")
            } catch {
                print("Error creating event: \(error)")
                handle(error: error)
            }
        }
    }

    private func confirmUpdateEvent(response: UpdateEventResponse, accessToken: String?) async {
        let metadata = response.metadata
        let eventID = metadata.event_id
        let calendarID = metadata.calendar_id

        Task { @MainActor in
            do {
                let token = try await resolveAccessToken(initial: accessToken)

                // Build update request from metadata (only include fields that are present)
                let timezone = TimeZone.autoupdatingCurrent.identifier
                let updateRequest = UpdateEventRequest(
                    summary: metadata.summary,
                    start: metadata.start?.dateTime,
                    end: metadata.end?.dateTime,
                    calendarId: calendarID,
                    description: metadata.description,
                    location: metadata.location,
                    timezone: timezone
                )

                // Call calendar service to apply the update
                _ = try await calendarService.updateEvent(
                    accessToken: token,
                    calendarId: calendarID,
                    eventId: eventID,
                    request: updateRequest
                )

                // Determine the day of the updated event using metadata if available
                if let startFromMetadata = metadata.start?.dateTime {
                    let eventDay = calendar.startOfDay(for: startFromMetadata)
                    loadSchedule(
                        for: eventDay,
                        force: true,
                        accessToken: token,
                        focusEvent: nil
                    )
                } else {
                    // Fallback: reload current schedule if we don't have a start date
                    loadCurrentDaySchedule(force: true)
                }

                print("Updated event: \(eventID)")
            } catch {
                print("Error updating event: \(error)")
                handle(error: error)
            }
        }
    }
    
    private func confirmDeleteEvent(response: DeleteEventResponse, accessToken: String?) async {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        
        Task { @MainActor in
            do {
                let token = try await resolveAccessToken(initial: accessToken)
                
                // Call the calendar service to delete the event
                try await calendarService.deleteEvent(
                    accessToken: token,
                    calendarId: calendarID,
                    eventId: eventID
                )
                
                // Clear focus event
                focusEvent = nil
                
                // Reload the schedule to reflect the deletion
                // Find the event to get its date for reloading
                if let targetEvent = displayEvents.first(where: { $0.event.id == eventID }),
                   let eventStartDate = targetEvent.event.start?.dateTime {
                    let eventDay = calendar.startOfDay(for: eventStartDate)
                    loadSchedule(
                        for: eventDay,
                        force: true,
                        accessToken: token,
                        focusEvent: nil
                    )
                } else {
                    // Fallback: reload current schedule
                    loadCurrentDaySchedule(force: true)
                }
                
                print("Deleted event: \(eventID)")
            } catch {
                print("Error deleting event: \(error)")
                handle(error: error)
            }
        }
    }

    // MARK: - Show Schedule Handling
    private func handleShowSchedule(agentResponse: AgentResponse, accessToken: String) async throws {
        let config = showScheduleHandler.configuration(for: agentResponse)
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

