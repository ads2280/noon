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
    private let timingLogger = TimingLogger.shared
    enum DisplayState {
        case idle
        case recording
        case uploading
        case completed(result: AgentActionResult)
        case failed(message: String)
    }
    
    struct AgentError {
        let message: String  // What went wrong
        let context: String  // Where it happened (e.g., "Agent processing", "Creating event")
    }

    @Published private(set) var displayState: DisplayState = .idle
    @Published private(set) var isRecording: Bool = false
    @Published private(set) var scheduleDate: Date
    @Published private(set) var displayEvents: [DisplayEvent]
    @Published private(set) var isLoadingSchedule: Bool = false
    @Published private(set) var hasLoadedSchedule: Bool = false
    @Published private(set) var focusEvent: ScheduleFocusEvent?
    @Published private(set) var userTimezone: String?
    @Published var agentAction: AgentAction?
    @Published var isConfirmingAction: Bool = false
    @Published var transcriptionText: String?
    @Published var noticeMessage: String?
    @Published var errorState: AgentError?
    
    private var noticeDismissTask: Task<Void, Never>?
    private var errorDismissTask: Task<Void, Never>?
    
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
    var numberOfDays: Int = 3

    private weak var authProvider: AuthSessionProviding?
    private let recorder: AgentAudioRecorder
    private let service: AgentActionServicing
    private let transcriptionService: TranscriptionServicing
    private let scheduleService: GoogleCalendarScheduleServicing
    private let calendarService: CalendarServicing
    private let showScheduleHandler: ShowScheduleActionHandling
    private let calendar: Foundation.Calendar = Foundation.Calendar.autoupdatingCurrent
    
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
        // Fetch user timezone when configuring
        Task {
            await fetchUserTimezone()
        }
    }
    
    func fetchUserTimezone() async {
        let timezone = await AuthTokenProvider.shared.fetchUserTimezone()
        await MainActor.run {
            self.userTimezone = timezone
        }
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
        errorState = nil // Clear any previous errors when starting new recording
        errorDismissTask?.cancel() // Cancel any pending error dismiss task

        Task { @MainActor in
            do {
                try await recorder.startRecording()
            } catch {
                // Recording errors are not agent/calendar action errors, use generic handler
                handle(error: error)
            }
        }
    }

    func stopAndSendRecording(accessToken: String?) {
        guard isRecording else { return }

        isRecording = false
        let flowStart = Date()

        Task { @MainActor in
            do {
                // Stop recording
                let stopStart = Date()
                guard let recording = try await recorder.stopRecording() else {
                    displayState = .idle
                    return
                }
                let stopDuration = Date().timeIntervalSince(stopStart)
                await timingLogger.logStep("frontend.stop_recording", duration: stopDuration)
                defer { try? FileManager.default.removeItem(at: recording.fileURL) }

                let startingToken = try await resolveAccessToken(initial: accessToken)

                displayState = .uploading
                
                // Step 1: Transcribe audio
                let transcribeStart = Date()
                let transcriptionResult = try await transcribeAudio(
                    recording: recording,
                    accessToken: startingToken
                )
                let transcribeDuration = Date().timeIntervalSince(transcribeStart)
                await timingLogger.logStep("frontend.transcribe_audio", duration: transcribeDuration, details: "text_length=\(transcriptionResult.text.count) chars")
                
                let transcribedText = transcriptionResult.text
                transcriptionText = transcribedText // Store transcription for display
                print("Transcribed: \"\(transcribedText)\"")
                
                // Clear any existing highlights, notices, or confirmations from previous agent action state
                agentAction = nil
                focusEvent = nil
                noticeMessage = nil
                
                // Step 2: Send to agent
                let agentStart = Date()
                let (result, tokenUsed) = try await sendToAgent(
                    query: transcribedText,
                    accessToken: startingToken
                )
                let agentDuration = Date().timeIntervalSince(agentStart)
                await timingLogger.logStep("frontend.send_to_agent", duration: agentDuration, details: "response_type=\(result.agentResponse.typeString)")

                // Step 3: Handle response and display UI
                let handleStart = Date()
                try await handle(agentResponse: result.agentResponse, accessToken: tokenUsed)
                let handleDuration = Date().timeIntervalSince(handleStart)
                await timingLogger.logStep("frontend.handle_response", duration: handleDuration)

                // Clear transcription text when agent response arrives
                transcriptionText = nil

                displayState = .completed(result: result)
                
                // Log total flow duration
                let totalDuration = Date().timeIntervalSince(flowStart)
                await timingLogger.logStep("frontend.total_flow", duration: totalDuration)
                
                // Set notice message for no-action responses (after clearing transcription)
                switch result.agentResponse {
                case .noAction(let response):
                    setNoticeMessage(response.metadata.reason)
                case .error(let error):
                    // Handle agent error - this is an agent mistake, not a user error
                    // Log full error details for debugging (verbose internal logging)
                    print("Agent error handled: \(error.message)")
                    // AgentErrorResponse conforms to Error, so we can pass it directly
                    // This will show brief, user-friendly message to user
                    handleAgentError(error as Error, context: "Agent processing")
                default:
                    // Clear notice message for successful actions
                    clearNoticeMessage()
                }

                if let responseString = result.responseString {
                    let formattedResponse = formatAgentResponse(
                        statusCode: result.statusCode,
                        jsonString: responseString
                    )
                    print(formattedResponse)
                }
            } catch {
                // Errors during agent action flow should use agent error handler
                handleAgentError(error, context: "Agent processing")
            }
        }
    }

    func reset() {
        displayState = .idle
        isRecording = false
        transcriptionText = nil
        clearNoticeMessage()
        errorState = nil
        errorDismissTask?.cancel()
    }
    
    private func setNoticeMessage(_ message: String) {
        // Don't override error state with notice messages
        guard errorState == nil else {
            return
        }
        
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
    
    private func formatAgentResponse(statusCode: Int, jsonString: String) -> String {
        guard let jsonData = jsonString.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else {
            return "Agent response: [Failed to parse JSON]"
        }
        
        var lines: [String] = []
        
        // Type
        if let type = json["type"] as? String {
            lines.append("Agent response: \(type)")
        } else {
            lines.append("Agent response: [unknown]")
        }
        
        // Metadata
        if let metadata = json["metadata"] as? [String: Any], !metadata.isEmpty {
            formatMetadata(metadata, into: &lines)
        }
        
        return lines.joined(separator: "\n")
    }
    
    private func formatMetadata(_ metadata: [String: Any], into lines: inout [String]) {
        for (key, value) in metadata.sorted(by: { $0.key < $1.key }) {
            let formattedKey = formatKey(key)
            let formattedValue = formatValue(value)
            lines.append("  \(formattedKey): \(formattedValue)")
        }
    }
    
    private func formatKey(_ key: String) -> String {
        // Convert snake_case to Title Case
        return key.split(separator: "_")
            .map { $0.capitalized }
            .joined(separator: " ")
    }
    
    private func formatValue(_ value: Any) -> String {
        switch value {
        case is NSNull:
            return "null"
        case let stringValue as String:
            // Format ISO date strings nicely
            if let date = parseISODate(stringValue) {
                let formatter = DateFormatter()
                formatter.dateStyle = .medium
                formatter.timeStyle = .short
                return formatter.string(from: date)
            }
            return stringValue
        case let numberValue as NSNumber:
            return "\(numberValue)"
        case let boolValue as Bool:
            return boolValue ? "true" : "false"
        case let arrayValue as [Any]:
            return "[\(arrayValue.count) item\(arrayValue.count == 1 ? "" : "s")]"
        case let dictValue as [String: Any]:
            // Handle nested dictionaries - especially for dateTime objects
            // Check for all-day event (has date string, dateTime is null)
            if let dateString = dictValue["date"] as? String,
               dictValue["dateTime"] is NSNull || dictValue["dateTime"] == nil {
                // All-day event - format as date only (no time)
                if let date = parseISODate(dateString) {
                    let formatter = DateFormatter()
                    formatter.dateStyle = .medium
                    formatter.timeStyle = .none  // No time for all-day events
                    return formatter.string(from: date)
                }
            }
            // Check for timed event (has dateTime string)
            if let dateTime = dictValue["dateTime"] as? String,
               let date = parseISODate(dateTime) {
                let formatter = DateFormatter()
                formatter.dateStyle = .medium
                formatter.timeStyle = .short
                return formatter.string(from: date)
            }
            // For other nested dicts, show key-value pairs inline
            let pairs = dictValue.map { (k, v) -> String in
                let formattedV = formatValueInline(v)
                return "\(k): \(formattedV)"
            }
            return pairs.isEmpty ? "{}" : "{ \(pairs.joined(separator: ", ")) }"
        default:
            return "\(value)"
        }
    }
    
    private func formatValueInline(_ value: Any) -> String {
        switch value {
        case is NSNull:
            return "null"
        case let stringValue as String:
            if let date = parseISODate(stringValue) {
                let formatter = DateFormatter()
                formatter.dateStyle = .medium
                formatter.timeStyle = .short
                return formatter.string(from: date)
            }
            return stringValue
        case let numberValue as NSNumber:
            return "\(numberValue)"
        case let boolValue as Bool:
            return boolValue ? "true" : "false"
        default:
            return "\(value)"
        }
    }
    
    private func parseISODate(_ string: String) -> Date? {
        // Try ISO8601DateFormatter first
        let iso8601Formatter = ISO8601DateFormatter()
        if let date = iso8601Formatter.date(from: string) {
            return date
        }
        
        // Try DateFormatter with common ISO formats
        let dateFormats = [
            "yyyy-MM-dd'T'HH:mm:ssZ",
            "yyyy-MM-dd'T'HH:mm:ss.SSSZ",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd"
        ]
        
        let dateFormatter = DateFormatter()
        for format in dateFormats {
            dateFormatter.dateFormat = format
            if let date = dateFormatter.date(from: string) {
                return date
            }
        }
        
        return nil
    }

    private func handle(error: Error) {
        // This method is only for non-agent/non-calendar action errors
        // For agent and calendar action errors, use handleAgentError or handleCalendarActionError
        
        // Log full error details for debugging (verbose internal logging)
        if let serverError = error as? ServerError {
            print("Request failed (\(serverError.statusCode)): \(serverError.message)")
        } else {
            print("Request failed: \(error.localizedDescription)")
        }
        
        // Show brief, user-friendly message (not technical details)
        let errorMessage = localizedMessage(for: error)
        displayState = .failed(message: errorMessage)
        // Only set notice if no error state is present
        if errorState == nil {
            setNoticeMessage(errorMessage)
        }
        isRecording = false
        // Keep transcriptionText visible even on error, as transcription may have succeeded
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

        let loadStart = Date()
        let dateRange = self.dateRange(for: date)
        
        let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
        let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
        
        let token = try await resolveAccessToken(initial: initialToken)
        let fetchStart = Date()
        let events = try await fetchScheduleEvents(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: token
        )
            let fetchDuration = Date().timeIntervalSince(fetchStart)
            await timingLogger.logStep("frontend.load_schedule.fetch_events", duration: fetchDuration, details: "event_count=\(events.count)")

        print("Loaded schedule: \(events.count) events")
        scheduleDate = dateRange.start
        displayEvents = events
        self.focusEvent = focusEvent
        hasLoadedSchedule = true
        
        let loadDuration = Date().timeIntervalSince(loadStart)
        await timingLogger.logStep("frontend.load_schedule", duration: loadDuration)
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
    
    // MARK: - Error Categorization
    
    private func categorizeError(_ error: Error, context: String) -> AgentError {
        var message: String
        
        // Categorize by error type
        if let agentErrorResponse = error as? AgentErrorResponse {
            // Agent error response from backend - use the message directly
            // This message should already be user-friendly from the backend
            let trimmedMessage = agentErrorResponse.message.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmedMessage.isEmpty {
                message = "Agent failed to handle request precisely. Please try rephrasing your request."
            } else {
                message = trimmedMessage
            }
        } else if let serverError = error as? ServerError {
            // First, check if the server error message is user-friendly (from backend)
            // Backend should return proper error messages in ServerError.message
            let backendMessage = serverError.message.trimmingCharacters(in: .whitespacesAndNewlines)
            
            // If backend provided a meaningful message, use it (but sanitize if needed)
            if !backendMessage.isEmpty && backendMessage != "Unknown error" {
                // Use backend message directly - it should already be user-friendly
                message = backendMessage
            } else {
                // Fallback to status code-based categorization
                switch serverError.statusCode {
                case 401, 403:
                    message = "Authentication failed"
                case 404:
                    message = "Resource not found"
                case 400...499:
                    message = "Request failed"
                case 500...599:
                    message = "Server error"
                default:
                    message = "Network error"
                }
            }
        } else if error is AccessTokenError {
            message = "Authentication failed"
        } else if error is CalendarServiceError || error is GoogleCalendarScheduleServiceError {
            message = "Calendar operation failed"
        } else if let urlError = error as? URLError {
            // Check for specific timeout error
            if urlError.code == .timedOut {
                message = "Request timed out."
            } else {
                message = "Network connection failed"
            }
        } else {
            // For other errors, try to use localizedDescription if available
            let errorDescription = error.localizedDescription
            if !errorDescription.isEmpty && errorDescription != "The operation couldn't be completed." {
                message = errorDescription
            } else {
                message = "Something went wrong"
            }
        }
        
        return AgentError(message: message, context: context)
    }
    
    // MARK: - Error Handling
    
    private func handleAgentError(_ error: Error, context: String = "Agent processing") {
        let errorState = categorizeError(error, context: context)
        self.errorState = errorState
        displayState = .failed(message: errorState.message)
        // Clear transcription/notice when showing error
        transcriptionText = nil
        noticeMessage = nil
        // Auto-dismiss error after 4 seconds
        scheduleErrorAutoDismiss()
    }
    
    private func handleCalendarActionError(_ error: Error, action: ConfirmationActionType, pendingAction: AgentAction? = nil) {
        let context: String
        switch action {
        case .createEvent: context = "Creating event"
        case .updateEvent: context = "Updating event"
        case .deleteEvent: context = "Deleting event"
        }
        let errorState = categorizeError(error, context: context)
        self.errorState = errorState
        // Don't set displayState to failed for calendar action errors
        // Error modal will be shown via errorState
        // Auto-dismiss error after 4 seconds
        scheduleErrorAutoDismiss()
        
        // Clear agent action state as if the action was canceled
        // This ensures schedule view highlights and temporary events don't linger
        if let action = pendingAction {
            clearActionState(for: action)
        }
    }
    
    /// Clears the state for a given action, similar to cancelPendingAction but doesn't require agentAction to be set
    private func clearActionState(for action: AgentAction) {
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
            
            // Unhide the original event - create new instance to ensure SwiftUI detects the change
            if let originalIndex = displayEvents.firstIndex(where: { $0.event.id == eventID && $0.isHidden }) {
                let originalEvent = displayEvents[originalIndex].event
                let originalStyle = displayEvents[originalIndex].style
                displayEvents[originalIndex] = DisplayEvent(
                    event: originalEvent,
                    style: originalStyle,
                    isHidden: false
                )
            }
            
            focusEvent = nil
        }
    }
    
    private func scheduleErrorAutoDismiss() {
        // Cancel any existing dismiss task
        errorDismissTask?.cancel()
        
        // Schedule new dismiss task for 4 seconds
        errorDismissTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 4_000_000_000) // 4 seconds
            if !Task.isCancelled {
                errorState = nil
            }
        }
    }
    
    func dismissError() {
        errorState = nil
    }

    private func handle(agentResponse: AgentResponse, accessToken: String) async throws {
        _ = Date()
        switch agentResponse {
        case .showEvent(let response):
            let actionStart = Date()
            try await handleShowEvent(response: response, accessToken: accessToken)
            let actionDuration = Date().timeIntervalSince(actionStart)
            await timingLogger.logStep("frontend.handle_response.show_event", duration: actionDuration)
        case .showSchedule:
            let actionStart = Date()
            try await handleShowSchedule(agentResponse: agentResponse, accessToken: accessToken)
            let actionDuration = Date().timeIntervalSince(actionStart)
            await timingLogger.logStep("frontend.handle_response.show_schedule", duration: actionDuration)
        case .deleteEvent(let response):
            let actionStart = Date()
            try await handleDeleteEvent(response: response, accessToken: accessToken)
            let actionDuration = Date().timeIntervalSince(actionStart)
            await timingLogger.logStep("frontend.handle_response.delete_event", duration: actionDuration)
        case .updateEvent(let response):
            let actionStart = Date()
            try await handleUpdateEvent(response: response, accessToken: accessToken)
            let actionDuration = Date().timeIntervalSince(actionStart)
            await timingLogger.logStep("frontend.handle_response.update_event", duration: actionDuration)
        case .createEvent(let response):
            let actionStart = Date()
            try await handleCreateEvent(response: response, accessToken: accessToken)
            let actionDuration = Date().timeIntervalSince(actionStart)
            await timingLogger.logStep("frontend.handle_response.create_event", duration: actionDuration)
        case .noAction(let response):
            setNoticeMessage(response.metadata.reason)
        case .error(let error):
            // Handle agent error - this is an agent mistake, not a user error
            // Log full error details for debugging (verbose internal logging)
            print("Agent error handled: \(error.message)")
            // AgentErrorResponse conforms to Error, so we can pass it directly
            // This will show brief, user-friendly message to user
            handleAgentError(error as Error, context: "Agent processing")
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
        
        let networkStart = Date()
        do {
            let result = try await transcriptionService.transcribe(
                request: request,
                accessToken: accessToken
            )
            let networkDuration = Date().timeIntervalSince(networkStart)
            await timingLogger.logStep("frontend.transcribe_audio.network", duration: networkDuration)
            return result
        } catch let error as ServerError where error.statusCode == 401 {
            // Token expired - refresh and retry once
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            let retryStart = Date()
            let result = try await transcriptionService.transcribe(
                request: request,
                accessToken: refreshedToken
            )
            let retryDuration = Date().timeIntervalSince(retryStart)
            await timingLogger.logStep("frontend.transcribe_audio.network_retry", duration: retryDuration)
            return result
        }
    }
    
    private func sendToAgent(
        query: String,
        accessToken: String
    ) async throws -> (AgentActionResult, String) {
        let request = AgentActionRequest(query: query)
        
        // Log total time from frontend perspective (includes all overhead)
        let totalStart = Date()
        await timingLogger.logStart("frontend.send_to_agent.total", details: "query_length=\(query.count) chars")
        
        let networkStart = Date()
        do {
            let result = try await service.performAgentAction(
                request: request,
                accessToken: accessToken
            )
            let networkDuration = Date().timeIntervalSince(networkStart)
            await timingLogger.logStep("frontend.send_to_agent.network", duration: networkDuration, details: "status_code=\(result.statusCode)")
            
            // Log total time (from frontend's perspective - includes network + any processing)
            let totalDuration = Date().timeIntervalSince(totalStart)
            await timingLogger.logStep("frontend.send_to_agent.total", duration: totalDuration, details: "response_type=\(result.agentResponse.typeString)")
            
            return (result, accessToken)
        } catch let error as ServerError where error.statusCode == 401 {
            // Token expired - refresh and retry once
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            let retryStart = Date()
            let result = try await service.performAgentAction(
                request: request,
                accessToken: refreshedToken
            )
            let retryDuration = Date().timeIntervalSince(retryStart)
            await timingLogger.logStep("frontend.send_to_agent.network_retry", duration: retryDuration, details: "status_code=\(result.statusCode)")
            
            // Log total time for retry
            let totalDuration = Date().timeIntervalSince(totalStart)
            await timingLogger.logStep("frontend.send_to_agent.total", duration: totalDuration, details: "response_type=\(result.agentResponse.typeString) retry=true")
            
            return (result, refreshedToken)
        }
    }

    private func fetchScheduleEvents(
        startDateISO: String,
        endDateISO: String,
        accessToken: String
    ) async throws -> [DisplayEvent] {
        // Try the request first
        let networkStart = Date()
        do {
            let schedule = try await scheduleService.fetchSchedule(
                startDateISO: startDateISO,
                endDateISO: endDateISO,
                accessToken: accessToken
            )
            let networkDuration = Date().timeIntervalSince(networkStart)
            await timingLogger.logStep("frontend.fetch_schedule_events.network", duration: networkDuration, details: "event_count=\(schedule.events.count)")
            return schedule.events.map { DisplayEvent(event: $0) }
        } catch GoogleCalendarScheduleServiceError.unauthorized {
            // Token expired - refresh and retry once
            guard let refreshedToken = await AuthTokenProvider.shared.currentAccessToken() else {
                throw AccessTokenError.missingAuthProvider
            }
            let retryStart = Date()
            let schedule = try await scheduleService.fetchSchedule(
                startDateISO: startDateISO,
                endDateISO: endDateISO,
                accessToken: refreshedToken
            )
            let retryDuration = Date().timeIntervalSince(retryStart)
            await timingLogger.logStep("frontend.fetch_schedule_events.network_retry", duration: retryDuration, details: "event_count=\(schedule.events.count)")
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
        let fetchStart = Date()
        let event = try await fetchEventWithRefresh(
            accessToken: accessToken,
            calendarId: calendarID,
            eventId: eventID
        )
        let fetchDuration = Date().timeIntervalSince(fetchStart)
        await timingLogger.logStep("frontend.handle_show_event.fetch_event", duration: fetchDuration)
        
        // Determine event day using enum pattern matching
        let eventDay: Date
        if let start = event.start {
            switch start.eventTime {
            case .timed(let dateTime, _):
                eventDay = calendar.startOfDay(for: dateTime)
            case .allDay(let dateString):
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                guard let startDate = dateFormatter.date(from: dateString) else {
                    print("ERROR: Event \(eventID) has invalid start date string: \(dateString)")
                    throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has invalid start date"])
                }
                eventDay = calendar.startOfDay(for: startDate)
            }
        } else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }

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
        
        // Determine event day using enum pattern matching
        let eventDay: Date
        if let start = event.start {
            switch start.eventTime {
            case .timed(let dateTime, _):
                eventDay = calendar.startOfDay(for: dateTime)
            case .allDay(let dateString):
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                guard let startDate = dateFormatter.date(from: dateString) else {
                    print("ERROR: Event \(eventID) has invalid start date string: \(dateString)")
                    throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has invalid start date"])
                }
                eventDay = calendar.startOfDay(for: startDate)
            }
        } else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }
        
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
        
        // Determine updated start date/time using enum pattern matching
        let updatedStart: CalendarEvent.EventDateTime?
        if let metadataStart = metadata.start {
            switch metadataStart {
            case .timed(let dateTime):
                updatedStart = CalendarEvent.EventDateTime(
                    eventTime: .timed(dateTime: dateTime, timeZone: timezone)
                )
            case .allDay(let date):
                updatedStart = CalendarEvent.EventDateTime(
                    eventTime: .allDay(date: date)
                )
            }
        } else {
            updatedStart = originalEvent.start
        }
        
        // Determine updated end date/time using enum pattern matching
        let updatedEnd: CalendarEvent.EventDateTime?
        if let metadataEnd = metadata.end {
            switch metadataEnd {
            case .timed(let dateTime):
                updatedEnd = CalendarEvent.EventDateTime(
                    eventTime: .timed(dateTime: dateTime, timeZone: timezone)
                )
            case .allDay(let date):
                updatedEnd = CalendarEvent.EventDateTime(
                    eventTime: .allDay(date: date)
                )
            }
        } else {
            updatedEnd = originalEvent.end
        }
        
        // Determine the day for the preview event using enum pattern matching
        let eventDay: Date
        if let metadataStart = metadata.start {
            switch metadataStart {
            case .timed(let dateTime):
                eventDay = calendar.startOfDay(for: dateTime)
            case .allDay(let dateString):
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                guard let startDate = dateFormatter.date(from: dateString) else {
                    print("ERROR: Event \(eventID) has invalid start date string: \(dateString)")
                    throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has invalid start date"])
                }
                eventDay = calendar.startOfDay(for: startDate)
            }
        } else if let originalStart = originalEvent.start {
            switch originalStart.eventTime {
            case .timed(let dateTime, _):
                eventDay = calendar.startOfDay(for: dateTime)
            case .allDay(let dateString):
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                guard let startDate = dateFormatter.date(from: dateString) else {
                    print("ERROR: Event \(eventID) has invalid original start date string: \(dateString)")
                    throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has invalid start date"])
                }
                eventDay = calendar.startOfDay(for: startDate)
            }
        } else {
            print("ERROR: Event \(eventID) has no start date")
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Event has no start date"])
        }
        
        // Fetch the schedule for that day
        let dateRange = self.dateRange(for: eventDay)
        let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
        let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
        
        var displayEvents = try await fetchScheduleEvents(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )
        
        // Look up calendar color: first try from original event, then from existing events, then from calendar list
        var calendarColor = originalEvent.calendarColor
        
        // If not found in original event, try from existing events
        if calendarColor == nil {
            calendarColor = displayEvents.first(where: { $0.event.calendarId == calendarID })?.event.calendarColor
        }
        
        // If still not found, fetch from calendar list
        if calendarColor == nil {
            do {
                let accounts = try await calendarService.fetchCalendars(accessToken: accessToken)
                // Find calendar by matching id (calendar_id from metadata is the Supabase calendar id)
                for account in accounts {
                    if let calendar = account.calendars?.first(where: { $0.id == calendarID || $0.googleCalendarId == calendarID }) {
                        calendarColor = calendar.color
                        break
                    }
                }
            } catch {
                // If calendar fetch fails, continue without color
            }
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
            calendarColor: calendarColor ?? originalEvent.calendarColor, // Use looked-up color or fall back to original
            location: metadata.location ?? originalEvent.location,
            conference: originalEvent.conference // Preserve conference
        )
        
        // Find and hide ALL instances of the original event in displayEvents
        // Match on event ID only (regardless of calendar) to ensure we hide the original event
        for index in displayEvents.indices.reversed() {
            if displayEvents[index].event.id == eventID && !displayEvents[index].isHidden {
                // Create a new DisplayEvent with isHidden=true to ensure SwiftUI detects the change
                let originalEvent = displayEvents[index].event
                let originalStyle = displayEvents[index].style
                displayEvents[index] = DisplayEvent(
                    event: originalEvent,
                    style: originalStyle,
                    isHidden: true
                )
            }
        }
        
        // Create preview DisplayEvent with .update style
        let previewDisplayEvent = DisplayEvent(event: previewEvent, style: .update, isHidden: false)
        displayEvents.append(previewDisplayEvent)
        
        // Sort events by start time (handle both all-day and timed events)
        displayEvents.sort { event1, event2 in
            let start1: Date?
            if let dateTime1 = event1.event.start?.dateTime {
                start1 = dateTime1
            } else if let dateString1 = event1.event.start?.date {
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                start1 = dateFormatter.date(from: dateString1)
            } else {
                start1 = nil
            }
            
            let start2: Date?
            if let dateTime2 = event2.event.start?.dateTime {
                start2 = dateTime2
            } else if let dateString2 = event2.event.start?.date {
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                dateFormatter.timeZone = calendar.timeZone
                start2 = dateFormatter.date(from: dateString2)
            } else {
                start2 = nil
            }
            
            guard let s1 = start1, let s2 = start2 else {
                return false
            }
            return s1 < s2
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
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        // Determine event day and create EventDateTime objects using enum pattern matching
        let eventDay: Date
        let startEventDateTime: CalendarEvent.EventDateTime
        let endEventDateTime: CalendarEvent.EventDateTime
        
        switch (metadata.start, metadata.end) {
        case (.allDay(let startDateString), .allDay(let endDateString)):
            // All-day event - parse date strings
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            dateFormatter.timeZone = calendar.timeZone
            guard let startDate = dateFormatter.date(from: startDateString) else {
                throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid start date format"])
            }
            eventDay = calendar.startOfDay(for: startDate)
            
            startEventDateTime = CalendarEvent.EventDateTime(
                eventTime: .allDay(date: startDateString)
            )
            endEventDateTime = CalendarEvent.EventDateTime(
                eventTime: .allDay(date: endDateString)
            )
        case (.timed(let startDateTime), .timed(let endDateTime)):
            // Timed event
            eventDay = calendar.startOfDay(for: startDateTime)
            
            startEventDateTime = CalendarEvent.EventDateTime(
                eventTime: .timed(dateTime: startDateTime, timeZone: timezone)
            )
            endEventDateTime = CalendarEvent.EventDateTime(
                eventTime: .timed(dateTime: endDateTime, timeZone: timezone)
            )
        default:
            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Start and end must both be timed or both be all-day events"])
        }
        
        // Fetch the schedule for that day
        let dateRange = self.dateRange(for: eventDay)
        let startDateISO = Self.iso8601DateFormatter.string(from: dateRange.start)
        let endDateISO = Self.iso8601DateFormatter.string(from: dateRange.end)
        
        var displayEvents = try await fetchScheduleEvents(
            startDateISO: startDateISO,
            endDateISO: endDateISO,
            accessToken: accessToken
        )
        
        // Look up calendar color: first try from existing events, then from calendar list
        var calendarColor = displayEvents.first(where: { $0.event.calendarId == metadata.calendar_id })?.event.calendarColor
        
        // If not found in events, fetch from calendar list
        if calendarColor == nil {
            do {
                let accounts = try await calendarService.fetchCalendars(accessToken: accessToken)
                // Find calendar by matching id (calendar_id from metadata is the Supabase calendar id)
                for account in accounts {
                    if let calendar = account.calendars?.first(where: { $0.id == metadata.calendar_id || $0.googleCalendarId == metadata.calendar_id }) {
                        calendarColor = calendar.color
                        break
                    }
                }
            } catch {
                // If calendar fetch fails, continue without color
            }
        }
        
        // Create a temporary CalendarEvent from the metadata
        let tempEventID = UUID().uuidString
        let tempEvent = CalendarEvent(
            id: tempEventID,
            title: metadata.summary,
            description: metadata.description,
            start: startEventDateTime,
            end: endEventDateTime,
            attendees: [],
            createdBy: nil,
            calendarId: metadata.calendar_id,
            calendarColor: calendarColor,
            location: metadata.location,
            conference: nil
        )
        
        // Add the temporary event to the display events with .new style
        let newDisplayEvent = DisplayEvent(event: tempEvent, style: .new)
        displayEvents.append(newDisplayEvent)
        
        // Sort events by start time using enum pattern matching
        displayEvents.sort { event1, event2 in
            let start1: Date?
            if let start = event1.event.start {
                switch start.eventTime {
                case .timed(let dateTime, _):
                    start1 = dateTime
                case .allDay(let dateString):
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    dateFormatter.timeZone = calendar.timeZone
                    start1 = dateFormatter.date(from: dateString)
                }
            } else {
                start1 = nil
            }
            
            let start2: Date?
            if let start = event2.event.start {
                switch start.eventTime {
                case .timed(let dateTime, _):
                    start2 = dateTime
                case .allDay(let dateString):
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    dateFormatter.timeZone = calendar.timeZone
                    start2 = dateFormatter.date(from: dateString)
                }
            } else {
                start2 = nil
            }
            
            guard let s1 = start1, let s2 = start2 else {
                return false
            }
            return s1 < s2
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
        
        // Store action before clearing it (needed for error cleanup)
        let pendingAction = action
        
        // Clear agent action immediately so modal disappears
        agentAction = nil
        
        isConfirmingAction = true
        defer { isConfirmingAction = false }
        
        switch action {
        case .showEvent, .showSchedule:
            // No confirmation needed for these actions
            break
        case .createEvent(let response):
            await confirmCreateEvent(response: response, accessToken: accessToken, pendingAction: pendingAction)
        case .deleteEvent(let response):
            await confirmDeleteEvent(response: response, accessToken: accessToken, pendingAction: pendingAction)
        case .updateEvent(let response):
            await confirmUpdateEvent(response: response, accessToken: accessToken, pendingAction: pendingAction)
        }
    }
    
    func cancelPendingAction() {
        guard let action = agentAction else { return }
        
        // Clear the state for this action
        clearActionState(for: action)
        
        // Clear agent action
        agentAction = nil
    }
    
    private func confirmCreateEvent(response: CreateEventResponse, accessToken: String?, pendingAction: AgentAction) async {
        let metadata = response.metadata
        let timezone = TimeZone.autoupdatingCurrent.identifier
        
        Task { @MainActor in
            do {
                var token = try await resolveAccessToken(initial: accessToken)
                
                // Build the create request from metadata using enum pattern matching
                let createRequest: CreateEventRequest
                switch (metadata.start, metadata.end) {
                case (.timed(let startDateTime), .timed(let endDateTime)):
                    // Timed event
                    createRequest = CreateEventRequest(
                        summary: metadata.summary,
                        start: BackendEventTime(timed: startDateTime, timeZone: timezone),
                        end: BackendEventTime(timed: endDateTime, timeZone: timezone),
                        calendarId: metadata.calendar_id,
                        description: metadata.description,
                        location: metadata.location,
                        timezone: timezone
                    )
                case (.allDay(let startDateString), .allDay(let endDateString)):
                    // All-day event
                    createRequest = CreateEventRequest(
                        summary: metadata.summary,
                        start: BackendEventTime(allDay: startDateString),
                        end: BackendEventTime(allDay: endDateString),
                        calendarId: metadata.calendar_id,
                        description: metadata.description,
                        location: metadata.location,
                        timezone: timezone
                    )
                default:
                    throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Start and end must both be timed or both be all-day events"])
                }
                
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
                
                // Determine event day from created event using enum pattern matching
                let eventDay: Date
                if let start = createdEvent.start {
                    switch start.eventTime {
                    case .timed(let dateTime, _):
                        eventDay = calendar.startOfDay(for: dateTime)
                    case .allDay(let dateString):
                        let dateFormatter = DateFormatter()
                        dateFormatter.dateFormat = "yyyy-MM-dd"
                        dateFormatter.timeZone = calendar.timeZone
                        guard let startDate = dateFormatter.date(from: dateString) else {
                            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid start date format"])
                        }
                        eventDay = calendar.startOfDay(for: startDate)
                    }
                } else {
                    // Fallback: use metadata to determine day
                    switch metadata.start {
                    case .timed(let dateTime):
                        eventDay = calendar.startOfDay(for: dateTime)
                    case .allDay(let dateString):
                        let dateFormatter = DateFormatter()
                        dateFormatter.dateFormat = "yyyy-MM-dd"
                        dateFormatter.timeZone = calendar.timeZone
                        guard let startDate = dateFormatter.date(from: dateString) else {
                            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid start date format"])
                        }
                        eventDay = calendar.startOfDay(for: startDate)
                    }
                }
                
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
                // Log full error details for debugging (verbose internal logging)
                print("Error creating event: \(error)")
                // Show brief, user-friendly message to user
                // Clear agent action state as if the action was canceled
                handleCalendarActionError(error, action: .createEvent, pendingAction: pendingAction)
            }
        }
    }

    private func confirmUpdateEvent(response: UpdateEventResponse, accessToken: String?, pendingAction: AgentAction) async {
        let metadata = response.metadata
        let eventID = metadata.event_id
        let calendarID = metadata.calendar_id

        Task { @MainActor in
            do {
                var token = try await resolveAccessToken(initial: accessToken)

                // Build update request from metadata using enum pattern matching
                let timezone = TimeZone.autoupdatingCurrent.identifier
                
                // Convert DateTimeDict to BackendEventTime
                let startBackendTime: BackendEventTime?
                if let start = metadata.start {
                    switch start {
                    case .timed(let dateTime):
                        startBackendTime = BackendEventTime(timed: dateTime, timeZone: timezone)
                    case .allDay(let date):
                        startBackendTime = BackendEventTime(allDay: date)
                    }
                } else {
                    startBackendTime = nil
                }
                
                let endBackendTime: BackendEventTime?
                if let end = metadata.end {
                    switch end {
                    case .timed(let dateTime):
                        endBackendTime = BackendEventTime(timed: dateTime, timeZone: timezone)
                    case .allDay(let date):
                        endBackendTime = BackendEventTime(allDay: date)
                    }
                } else {
                    endBackendTime = nil
                }
                
                let updateRequest = UpdateEventRequest(
                    summary: metadata.summary,
                    start: startBackendTime,
                    end: endBackendTime,
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

                // Determine the day of the updated event using enum pattern matching
                // First try metadata (if start time was updated), otherwise fetch the event
                let eventStartDate: Date
                if let startFromMetadata = metadata.start {
                    switch startFromMetadata {
                    case .timed(let dateTime):
                        eventStartDate = dateTime
                    case .allDay(let dateString):
                        let dateFormatter = DateFormatter()
                        dateFormatter.dateFormat = "yyyy-MM-dd"
                        dateFormatter.timeZone = calendar.timeZone
                        guard let parsedDate = dateFormatter.date(from: dateString) else {
                            print("ERROR: Updated event \(eventID) has invalid start date string: \(dateString)")
                            throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Updated event has invalid start date"])
                        }
                        eventStartDate = parsedDate
                    }
                } else {
                    // Fetch the updated event to get its current start date
                    let updatedEvent = try await calendarService.fetchEvent(
                        accessToken: token,
                        calendarId: calendarID,
                        eventId: eventID
                    )
                    if let start = updatedEvent.start {
                        switch start.eventTime {
                        case .timed(let dateTime, _):
                            eventStartDate = dateTime
                        case .allDay(let dateString):
                            let dateFormatter = DateFormatter()
                            dateFormatter.dateFormat = "yyyy-MM-dd"
                            dateFormatter.timeZone = calendar.timeZone
                            guard let parsedDate = dateFormatter.date(from: dateString) else {
                                print("ERROR: Updated event \(eventID) has invalid start date string: \(dateString)")
                                throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Updated event has invalid start date"])
                            }
                            eventStartDate = parsedDate
                        }
                    } else {
                        print("ERROR: Updated event \(eventID) has no start date")
                        throw NSError(domain: "AgentViewModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Updated event has no start date"])
                    }
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
                // Log full error details for debugging (verbose internal logging)
                print("Error updating event: \(error)")
                // Show brief, user-friendly message to user
                // Clear agent action state as if the action was canceled
                handleCalendarActionError(error, action: .updateEvent, pendingAction: pendingAction)
            }
        }
    }
    
    private func confirmDeleteEvent(response: DeleteEventResponse, accessToken: String?, pendingAction: AgentAction) async {
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
                // Find the event to get its date for reloading using enum pattern matching
                if let targetEvent = displayEvents.first(where: { $0.event.id == eventID }) {
                    let eventDay: Date?
                    if let start = targetEvent.event.start {
                        switch start.eventTime {
                        case .timed(let dateTime, _):
                            eventDay = calendar.startOfDay(for: dateTime)
                        case .allDay(let dateString):
                            let dateFormatter = DateFormatter()
                            dateFormatter.dateFormat = "yyyy-MM-dd"
                            dateFormatter.timeZone = calendar.timeZone
                            eventDay = dateFormatter.date(from: dateString).map { calendar.startOfDay(for: $0) }
                        }
                    } else {
                        eventDay = nil
                    }
                    
                    if let eventDay = eventDay {
                        try await loadSchedule(
                            for: eventDay,
                            force: true,
                            accessToken: token,
                            focusEvent: nil
                        )
                    } else {
                        // Fallback: reload current schedule
                        let today = Date()
                        try await loadSchedule(for: today, force: true, accessToken: token)
                    }
                } else {
                    // Fallback: reload current schedule
                    let today = Date()
                    try await loadSchedule(for: today, force: true, accessToken: token)
                }
                
                print("Deleted event: \(eventID)")
            } catch {
                // Log full error details for debugging (verbose internal logging)
                print("Error deleting event: \(error)")
                // Show brief, user-friendly message to user
                // Clear agent action state as if the action was canceled
                handleCalendarActionError(error, action: .deleteEvent, pendingAction: pendingAction)
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

