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
    @Published var agentAction: AgentAction?
    @Published var isConfirmingAction: Bool = false
    @Published var transcriptionText: String?
    @Published var noticeMessage: String?
    
    private var noticeDismissTask: Task<Void, Never>?
    
    enum AgentAction {
        case showEvent(ShowEventResponse)
        case showSchedule(ShowScheduleResponse)
        case createEvent(CreateEventResponse)
        case updateEvent(UpdateEventResponse)
        case deleteEvent(DeleteEventResponse)
        
        /// Whether this action requires user confirmation via modal
        var requiresConfirmation: Bool {
            switch self {
            case .showEvent, .showSchedule:
                return false
            case .createEvent, .updateEvent, .deleteEvent:
                return true
            }
        }
        
        /// The focus event for schedule UI styling, if applicable
        var focusEvent: ScheduleFocusEvent? {
            switch self {
            case .showEvent(let response):
                return ScheduleFocusEvent(eventID: response.metadata.event_id, style: .highlight)
            case .showSchedule:
                return nil
            case .createEvent:
                // For create, we use a temporary event ID that's generated in handleCreateEvent
                // This will be set separately when the action is created
                return nil
            case .updateEvent(let response):
                return ScheduleFocusEvent(eventID: response.metadata.event_id, style: .update)
            case .deleteEvent(let response):
                return ScheduleFocusEvent(eventID: response.metadata.event_id, style: .destructive)
            }
        }
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
        
        // Pre-warm audio session to eliminate delay on first recording
        self.recorder.prewarm()
    }

    func configure(authProvider: AuthSessionProviding) {
        self.authProvider = authProvider
    }
    
    func cleanupAudioSession() {
        recorder.cleanup()
    }

    func startRecording() {
        guard isRecording == false else { return }

        isRecording = true
        displayState = .recording
        transcriptionText = nil // Clear previous transcription when starting new recording
        noticeMessage = nil // Clear previous notice when starting new recording

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
                transcriptionText = transcribedText // Store transcription for display
                print("Transcribed: \"\(transcribedText)\"")
                
                // Clear any existing highlights, notices, or confirmations from previous agent action state
                agentAction = nil
                focusEvent = nil
                noticeMessage = nil
                
                // Step 2: Send to agent
                let (result, tokenUsed) = try await sendToAgent(
                    query: transcribedText,
                    accessToken: startingToken
                )

                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)

                // Clear transcription text when agent response arrives
                transcriptionText = nil

                displayState = .completed(result: result)
                
                // Set notice message for no-action and error responses (after clearing transcription)
                switch result.agentResponse {
                case .noAction(let response):
                    setNoticeMessage(response.metadata.reason)
                    print("Notice message set for no-action: \(response.metadata.reason)")
                case .error(let error):
                    setNoticeMessage(error.message)
                    print("Notice message set for error: \(error.message)")
                default:
                    // Clear notice message for successful actions
                    clearNoticeMessage()
                }

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
        transcriptionText = nil
        clearNoticeMessage()
    }
    
    private func setNoticeMessage(_ message: String) {
        // Cancel any existing dismiss task
        noticeDismissTask?.cancel()
        
        // Set the notice message
        noticeMessage = message
        
        // Schedule automatic dismissal after 2 seconds
        noticeDismissTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
            if !Task.isCancelled {
                noticeMessage = nil
            }
        }
    }
    
    private func clearNoticeMessage() {
        noticeDismissTask?.cancel()
        noticeDismissTask = nil
        noticeMessage = nil
    }

    private func handle(error: Error) {
        let errorMessage = localizedMessage(for: error)
        displayState = .failed(message: errorMessage)
        setNoticeMessage(errorMessage)
        isRecording = false
        // Keep transcriptionText visible even on error, as transcription may have succeeded
        if let serverError = error as? ServerError {
            print("Request failed (\(serverError.statusCode)): \(serverError.message)")
        } else {
            print("Request failed: \(error.localizedDescription)")
        }
    }

    func loadCurrentDaySchedule(force: Bool = false) async throws {
        let today = Date()
        try await loadSchedule(for: today, force: force)
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
    ) async throws {
        guard isLoadingSchedule == false else {
            return
        }
        if force == false, calendar.isDate(scheduleDate, inSameDayAs: date), isLoadingSchedule {
            return
        }

        isLoadingSchedule = true
        defer {
            isLoadingSchedule = false
        }

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
        case .noAction(let response):
            setNoticeMessage(response.metadata.reason)
            print("Setting notice message for no-action: \(response.metadata.reason)")
        case .error(let error):
            setNoticeMessage(error.message)
            print("Setting notice message for error: \(error.message)")
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

    private func fetchEventWithRefresh(
        accessToken: String,
        calendarId: String,
        eventId: String
    ) async throws -> CalendarEvent {
        do {
            return try await calendarService.fetchEvent(
                accessToken: accessToken,
                calendarId: calendarId,
                eventId: eventId
            )
        } catch CalendarServiceError.unauthorized {
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            return try await calendarService.fetchEvent(
                accessToken: refreshedToken,
                calendarId: calendarId,
                eventId: eventId
            )
        }
    }

    // MARK: - Show Event Handling
    private func handleShowEvent(response: ShowEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        
        // Calculate focus event from response (before setting agentAction)
        let focus = ScheduleFocusEvent(eventID: eventID, style: .highlight)
        
        // Fetch the event to get its start date
        let event = try await fetchEventWithRefresh(
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

        // Load schedule for the event's day with focus event
        try await loadSchedule(
            for: eventDay,
            force: true,
            accessToken: accessToken,
            focusEvent: focus
        )
        
        // Set the unified agent action state AFTER schedule is ready
        // This ensures transcription stays visible until schedule is ready
        self.agentAction = .showEvent(response)
    }

    // MARK: - Delete Event Handling
    private func handleDeleteEvent(response: DeleteEventResponse, accessToken: String) async throws {
        let eventID = response.metadata.event_id
        let calendarID = response.metadata.calendar_id
        
        // Calculate focus event from response (before setting agentAction)
        let focus = ScheduleFocusEvent(eventID: eventID, style: .destructive)
        
        // Fetch the event to get its start date
        let event = try await fetchEventWithRefresh(
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
        
        // Load schedule for the event's day with focus event
        try await loadSchedule(
            for: eventDay,
            force: true,
            accessToken: accessToken,
            focusEvent: focus
        )
        
        // Set the unified agent action state AFTER schedule is ready
        // This ensures modal only appears once schedule and transcription are coordinated
        self.agentAction = .deleteEvent(response)
    }

    // MARK: - Update Event Handling
    private func handleUpdateEvent(response: UpdateEventResponse, accessToken: String) async throws {
        let metadata = response.metadata
        let eventID = metadata.event_id
        let calendarID = metadata.calendar_id
        
        // Fetch the original event to get its current data
        let originalEvent = try await fetchEventWithRefresh(
            accessToken: accessToken,
            calendarId: calendarID,
            eventId: eventID
        )
        
        // Create a merged CalendarEvent by applying update metadata to original event
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        // Determine updated start date/time
        let updatedStart: CalendarEvent.EventDateTime?
        if let metadataStart = metadata.start?.dateTime {
            updatedStart = CalendarEvent.EventDateTime(
                dateTime: metadataStart,
                date: nil,
                timeZone: timezone
            )
        } else {
            updatedStart = originalEvent.start
        }
        
        // Determine updated end date/time
        let updatedEnd: CalendarEvent.EventDateTime?
        if let metadataEnd = metadata.end?.dateTime {
            updatedEnd = CalendarEvent.EventDateTime(
                dateTime: metadataEnd,
                date: nil,
                timeZone: timezone
            )
        } else {
            updatedEnd = originalEvent.end
        }
        
        // Create merged event with updated fields
        // Use a temporary ID for the preview event (similar to create event flow)
        let tempEventID = UUID().uuidString
        let previewEvent = CalendarEvent(
            id: tempEventID, // Use temporary ID for preview
            title: metadata.summary ?? originalEvent.title,
            description: metadata.description ?? originalEvent.description,
            start: updatedStart,
            end: updatedEnd,
            attendees: originalEvent.attendees, // Preserve attendees
            createdBy: originalEvent.createdBy, // Preserve createdBy
            calendarId: calendarID,
            location: metadata.location ?? originalEvent.location,
            conference: originalEvent.conference // Preserve conference
        )
        
        // Determine the day for the preview event (use updated start if available, otherwise original)
        let previewStartDate = metadata.start?.dateTime ?? originalEvent.start?.dateTime
        guard let eventStartDate = previewStartDate else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }
        
        let eventDay = calendar.startOfDay(for: eventStartDate)
        
        // Fetch the schedule for that day
        let dateRange = self.dateRange(for: eventDay)
        let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
        let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
        
        var displayEvents = try await fetchScheduleEvents(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )
        
        // Find and hide the original event in displayEvents
        if let originalIndex = displayEvents.firstIndex(where: { $0.event.id == eventID }) {
            displayEvents[originalIndex].isHidden = true
        }
        
        // Create preview DisplayEvent with .update style
        let previewDisplayEvent = DisplayEvent(event: previewEvent, style: .update, isHidden: false)
        displayEvents.append(previewDisplayEvent)
        
        // Sort events by start time
        displayEvents.sort { event1, event2 in
            guard let start1 = event1.event.start?.dateTime,
                  let start2 = event2.event.start?.dateTime else {
                return false
            }
            return start1 < start2
        }
        
        // Set focus event with .update style (using preview event ID)
        let focus = ScheduleFocusEvent(eventID: tempEventID, style: .update)
        
        // Update the schedule state directly
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        // Set the unified agent action state AFTER schedule is ready
        // This ensures modal only appears once schedule and transcription are coordinated
        self.agentAction = .updateEvent(response)
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
        
        // Set focus event with .new style (using temp event ID)
        let focus = ScheduleFocusEvent(eventID: tempEventID, style: .new)
        
        // Update the schedule state directly
        scheduleDate = dateRange.start
        self.displayEvents = displayEvents
        self.focusEvent = focus
        hasLoadedSchedule = true
        
        // Set the unified agent action state AFTER schedule is ready
        // This ensures modal only appears once schedule and transcription are coordinated
        self.agentAction = .createEvent(response)
    }

    // MARK: - Event Confirmation
    func confirmPendingAction(accessToken: String?) async {
        guard let action = agentAction else {
            return
        }
        
        // Clear agent action immediately so modal disappears
        agentAction = nil
        
        isConfirmingAction = true
        defer { isConfirmingAction = false }
        
        switch action {
        case .showEvent, .showSchedule:
            // No confirmation needed for these actions
            break
        case .createEvent(let response):
            await confirmCreateEvent(response: response, accessToken: accessToken)
        case .deleteEvent(let response):
            await confirmDeleteEvent(response: response, accessToken: accessToken)
        case .updateEvent(let response):
            await confirmUpdateEvent(response: response, accessToken: accessToken)
        }
    }
    
    func cancelPendingAction() {
        guard let action = agentAction else { return }
        
        switch action {
        case .showEvent, .showSchedule:
            // Clear focus for show actions
            focusEvent = nil
        case .createEvent:
            // Remove the temporary event from display events
            if let tempEventID = focusEvent?.eventID,
               let tempEventIndex = displayEvents.firstIndex(where: { $0.event.id == tempEventID }) {
                displayEvents.remove(at: tempEventIndex)
                focusEvent = nil
            }
        case .deleteEvent:
            // Clear the focus event to remove special styling
            focusEvent = nil
        case .updateEvent(let response):
            // Remove the preview event and unhide the original event
            let eventID = response.metadata.event_id
            
            // Remove the preview event (identified by focusEvent ID)
            if let previewEventID = focusEvent?.eventID,
               let previewIndex = displayEvents.firstIndex(where: { $0.event.id == previewEventID }) {
                displayEvents.remove(at: previewIndex)
            }
            
            // Unhide the original event
            if let originalIndex = displayEvents.firstIndex(where: { $0.event.id == eventID && $0.isHidden }) {
                displayEvents[originalIndex].isHidden = false
            }
            
            focusEvent = nil
        }
        
        // Clear agent action
        agentAction = nil
    }
    
    private func confirmCreateEvent(response: CreateEventResponse, accessToken: String?) async {
        let metadata = response.metadata
        let startDate = metadata.start.dateTime
        let endDate = metadata.end.dateTime
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        Task { @MainActor in
            do {
                var token = try await resolveAccessToken(initial: accessToken)
                
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
                let createdResponse: CalendarCreateEventResponse
                do {
                    createdResponse = try await calendarService.createEvent(
                        accessToken: token,
                        request: createRequest
                    )
                } catch CalendarServiceError.unauthorized {
                    guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                        throw AccessTokenError.missingAuthProvider
                    }
                    token = refreshedToken
                    createdResponse = try await calendarService.createEvent(
                        accessToken: token,
                        request: createRequest
                    )
                }
                
                // Reload the schedule to get the real event from Google Calendar
                // This ensures the event displays properly without the .new style
                let createdEvent = createdResponse.event
                let createdEventID = createdEvent.id
                let eventDay = calendar.startOfDay(for: startDate)
                
                // Reload schedule for the day of the created event
                // No focus event - display normally without special styling
                try await loadSchedule(
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
                var token = try await resolveAccessToken(initial: accessToken)

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
                do {
                    _ = try await calendarService.updateEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID,
                        request: updateRequest
                    )
                } catch CalendarServiceError.unauthorized {
                    guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                        throw AccessTokenError.missingAuthProvider
                    }
                    token = refreshedToken
                    _ = try await calendarService.updateEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID,
                        request: updateRequest
                    )
                }

                // Determine the day of the updated event
                // First try metadata (if start time was updated), otherwise fetch the event
                let eventStartDate: Date
                if let startFromMetadata = metadata.start?.dateTime {
                    eventStartDate = startFromMetadata
                } else {
                    // Fetch the updated event to get its current start date
                    let updatedEvent = try await calendarService.fetchEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID
                    )
                    guard let startDate = updatedEvent.start?.dateTime else {
                        print("ERROR: Updated event \(eventID) has no start date")
                        throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Updated event has no start date"])
                    }
                    eventStartDate = startDate
                }
                
                // Reload schedule for the event's day
                let eventDay = calendar.startOfDay(for: eventStartDate)
                try await loadSchedule(
                    for: eventDay,
                    force: true,
                    accessToken: token,
                    focusEvent: nil
                )

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
                var token = try await resolveAccessToken(initial: accessToken)
                
                // Call the calendar service to delete the event
                do {
                    try await calendarService.deleteEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID
                    )
                } catch CalendarServiceError.unauthorized {
                    guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                        throw AccessTokenError.missingAuthProvider
                    }
                    token = refreshedToken
                    try await calendarService.deleteEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID
                    )
                }
                
                // Clear focus event
                focusEvent = nil
                
                // Reload the schedule to reflect the deletion
                // Find the event to get its date for reloading
                if let targetEvent = displayEvents.first(where: { $0.event.id == eventID }),
                   let eventStartDate = targetEvent.event.start?.dateTime {
                    let eventDay = calendar.startOfDay(for: eventStartDate)
                    try await loadSchedule(
                        for: eventDay,
                        force: true,
                        accessToken: token,
                        focusEvent: nil
                    )
                } else {
                    // Fallback: reload current schedule
                    let today = Date()
                    try await loadSchedule(for: today, force: true)
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
        guard case .showSchedule(let response) = agentResponse else {
            return
        }
        
        let config = showScheduleHandler.configuration(for: agentResponse)
        try await loadSchedule(
            for: config.date,
            force: true,
            accessToken: accessToken,
            focusEvent: config.focusEvent
        )
        
        // Set the unified agent action state AFTER schedule is ready
        // This ensures transcription stays visible until schedule is ready
        self.agentAction = .showSchedule(response)
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

