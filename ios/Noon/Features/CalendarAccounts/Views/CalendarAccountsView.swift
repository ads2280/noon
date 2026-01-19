//
//  CalendarAccountsView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct CalendarAccountsView: View {
    @StateObject private var viewModel: CalendarAccountsViewModel
    @StateObject private var coordinator = CalendarOAuthCoordinator()

    init(authViewModel: AuthViewModel, calendarService: CalendarServicing? = nil) {
        self.init(sessionProvider: authViewModel, calendarService: calendarService)
    }

    init(sessionProvider: AuthSessionProviding, calendarService: CalendarServicing? = nil) {
        _viewModel = StateObject(
            wrappedValue: CalendarAccountsViewModel(
                sessionProvider: sessionProvider,
                calendarService: calendarService
            )
        )
    }

    @State private var accountPendingDeletion: GoogleAccount?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                content
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 24)
            .padding(.vertical, 32)
        }
        .background(ColorPalette.Surface.background.ignoresSafeArea())
        .navigationTitle("Calendar Accounts")
        .toolbarTitleDisplayMode(.inline)
        .task {
            await viewModel.loadCalendars()
        }
        .alert("Remove account?", isPresented: Binding(
            get: { accountPendingDeletion != nil },
            set: { isPresented in
                if isPresented == false {
                    accountPendingDeletion = nil
                }
            }
        )) {
            Button("Remove", role: .destructive) {
                if let account = accountPendingDeletion {
                    Task {
                        await viewModel.deleteAccount(account)
                    }
                }
                accountPendingDeletion = nil
            }
            Button("Cancel", role: .cancel) {
                accountPendingDeletion = nil
            }
        } message: {
            if let account = accountPendingDeletion {
                Text("This will disconnect \(account.email) from Noon.")
            }
        }
        .alert("Unable to remove account", isPresented: Binding(
            get: { viewModel.deletionError != nil },
            set: { isPresented in
                if isPresented == false {
                    viewModel.clearDeletionError()
                }
            }
        )) {
            Button("OK", role: .cancel) {
                viewModel.clearDeletionError()
            }
        } message: {
            Text(viewModel.deletionError ?? "")
        }
    }
}

private extension CalendarAccountsView {
    var connectInlineButton: some View {
        Button {
            Task {
                await viewModel.linkCalendar(using: coordinator)
            }
        } label: {
            HStack(spacing: 10) {
                if viewModel.isLinking {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(ColorPalette.Text.secondary)
                        .scaleEffect(0.85, anchor: .center)
                } else {
                    Image(systemName: "plus")
                        .imageScale(.medium)
                        .font(.system(size: 16, weight: .semibold))
                }
                Text(viewModel.isLinking ? "Connecting…" : "Connect account")
                    .font(.callout.weight(.semibold))
            }
            .padding(.vertical, 10)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(ColorPalette.Surface.elevated.opacity(0.9))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(ColorPalette.Surface.overlay.opacity(0.5), lineWidth: 1)
            )
            .foregroundStyle(ColorPalette.Text.primary)
        }
        .buttonStyle(.plain)
        .disabled(viewModel.isLinking)
        .accessibilityIdentifier("connect-google-calendar")
    }

    @ViewBuilder
    var content: some View {
        if !viewModel.accounts.isEmpty {
            accountsList
        }

        connectInlineButton
            .padding(.top, 4)
    }

    var accountsList: some View {
        VStack(spacing: 12) {
            ForEach(viewModel.accounts, id: \.self) { account in
                accountRow(account)
            }
        }
    }

    func accountRow(_ account: GoogleAccount) -> some View {
        VStack(spacing: 0) {
            // Account header row
            HStack(spacing: 16) {
                Text(account.email)
                    .font(.headline)
                    .foregroundStyle(ColorPalette.Text.primary)
                    .lineLimit(1)
                    .truncationMode(.middle)

                Spacer()
                
                // Chevron icon
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(ColorPalette.Text.secondary)
                    .rotationEffect(.degrees(viewModel.isExpanded(account) ? 90 : 0))
                    .animation(.easeInOut(duration: 0.2), value: viewModel.isExpanded(account))

                if viewModel.isDeleting(account) {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(ColorPalette.Text.secondary)
                        .padding(.leading, 8)
                } else {
                    Button {
                        accountPendingDeletion = account
                    } label: {
                        Image(systemName: "trash.fill")
                            .imageScale(.medium)
                            .font(.system(size: 18, weight: .semibold))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(ColorPalette.Semantic.destructive)
                    .accessibilityLabel("Remove \(account.email)")
                    .padding(.leading, 8)
                }
            }
            .padding(.vertical, 18)
            .padding(.horizontal, 20)
            .contentShape(Rectangle())
            .onTapGesture {
                viewModel.toggleExpansion(for: account.id)
            }
            
            // Calendar list (shown when expanded)
            if viewModel.isExpanded(account) {
                let calendars = account.calendars ?? []
                VStack(spacing: 0) {
                    Divider()
                        .padding(.horizontal, 20)
                    
                    if calendars.isEmpty {
                        Text("No calendars")
                            .font(.subheadline)
                            .foregroundStyle(ColorPalette.Text.secondary)
                            .padding(.vertical, 12)
                            .padding(.horizontal, 20)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        VStack(spacing: 12) {
                            ForEach(calendars, id: \.id) { calendar in
                                calendarRow(calendar)
                            }
                        }
                        .padding(.vertical, 12)
                        .padding(.horizontal, 20)
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(ColorPalette.Surface.elevated.opacity(0.85))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(ColorPalette.Surface.overlay.opacity(0.4), lineWidth: 1)
        )
        .animation(.easeInOut(duration: 0.2), value: viewModel.isExpanded(account))
    }
    
    func calendarRow(_ calendar: GoogleCalendar) -> some View {
        HStack(spacing: 12) {
            // Color swatch for calendar
            Circle()
                .fill(Color.fromHex(calendar.color))
                .frame(width: 20, height: 20)
            
            Text(calendar.name)
                .font(.subheadline)
                .foregroundStyle(ColorPalette.Text.primary)
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            if calendar.isPrimary {
                Text("Primary")
                    .font(.caption)
                    .foregroundStyle(ColorPalette.Text.secondary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(
                        Capsule()
                            .fill(ColorPalette.Surface.overlay.opacity(0.3))
                    )
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    func successBanner(_ message: String) -> some View { EmptyView() }

    func errorBanner(_ message: String) -> some View { EmptyView() }
}

#Preview {
    let session = OTPSession(accessToken: "token", refreshToken: "refresh", tokenType: "bearer", expiresIn: 3600)
    let sessionProvider = MockSessionProvider(session: session)
    return NavigationStack {
        CalendarAccountsView(sessionProvider: sessionProvider, calendarService: MockCalendarService())
    }
    .preferredColorScheme(.dark)
}

private final class MockCalendarService: CalendarServicing {
    private var accounts: [GoogleAccount]

    init(accounts: [GoogleAccount] = [
            GoogleAccount(
                id: UUID().uuidString,
                userId: UUID().uuidString,
                googleUserId: "primary",
                email: "alex@example.com",
                displayName: "Alex Primary Calendar",
                avatarURL: nil,
                createdAt: Date().addingTimeInterval(-86_400 * 4),
                updatedAt: Date().addingTimeInterval(-3_600)
            ),
            GoogleAccount(
                id: UUID().uuidString,
                userId: UUID().uuidString,
                googleUserId: "work",
                email: "alex@work.com",
                displayName: "Work",
                avatarURL: nil,
                createdAt: Date().addingTimeInterval(-86_400 * 20),
                updatedAt: Date().addingTimeInterval(-9_000)
            ),
    ]) {
        self.accounts = accounts
    }

    func fetchCalendars(accessToken: String) async throws -> [GoogleAccount] {
        accounts
    }

    func refreshCalendars(accessToken: String) async throws {
        // Mock implementation - no-op for testing
    }

    func beginGoogleOAuth(accessToken: String) async throws -> GoogleOAuthStart {
        GoogleOAuthStart(
            authorizationURL: URL(string: "https://accounts.google.com/o/oauth2/v2/auth?mock=true")!,
            state: "mock-state",
            stateExpiresAt: Date().addingTimeInterval(300)
        )
    }

    func deleteCalendar(accessToken: String, accountId: String) async throws {
        accounts.removeAll { $0.id == accountId }
    }

    func createEvent(accessToken: String, request: CreateEventRequest) async throws -> CalendarCreateEventResponse {
        // Mock implementation - return a mock event
        let startEventTime: CalendarEvent.EventTime
        let endEventTime: CalendarEvent.EventTime
        
        // Convert BackendEventTime to CalendarEvent.EventTime
        switch request.start.type {
        case .timed:
            if let startDateTime = request.start.dateTime {
                startEventTime = .timed(dateTime: startDateTime, timeZone: request.start.timeZone)
            } else {
                let now = Date()
                startEventTime = .timed(dateTime: now, timeZone: request.timezone)
            }
        case .allDay:
            if let startDate = request.start.date {
                startEventTime = .allDay(date: startDate)
            } else {
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                formatter.timeZone = TimeZone(secondsFromGMT: 0)
                startEventTime = .allDay(date: formatter.string(from: Date()))
            }
        }
        
        switch request.end.type {
        case .timed:
            if let endDateTime = request.end.dateTime {
                endEventTime = .timed(dateTime: endDateTime, timeZone: request.end.timeZone)
            } else {
                let now = Date()
                endEventTime = .timed(dateTime: now.addingTimeInterval(3600), timeZone: request.timezone)
            }
        case .allDay:
            if let endDate = request.end.date {
                endEventTime = .allDay(date: endDate)
            } else {
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                formatter.timeZone = TimeZone(secondsFromGMT: 0)
                endEventTime = .allDay(date: formatter.string(from: Date().addingTimeInterval(86400)))
            }
        }
        
        let mockEvent = CalendarEvent(
            id: UUID().uuidString,
            title: request.summary,
            description: request.description,
            start: CalendarEvent.EventDateTime(eventTime: startEventTime),
            end: CalendarEvent.EventDateTime(eventTime: endEventTime),
            attendees: [],
            createdBy: nil,
            calendarId: request.calendarId,
            location: request.location,
            conference: nil
        )
        return CalendarCreateEventResponse(event: mockEvent)
    }

    func deleteEvent(accessToken: String, calendarId: String, eventId: String) async throws {
        // Mock implementation - just return success
        print("Mock deleted event: \(eventId)")
    }

    func fetchEvent(accessToken: String, calendarId: String, eventId: String) async throws -> CalendarEvent {
        // Mock implementation - return a mock event
        let now = Date()
        return CalendarEvent(
            id: eventId,
            title: "Mock Event",
            description: "This is a mock event for testing",
            start: CalendarEvent.EventDateTime(
                dateTime: now,
                date: nil,
                timeZone: TimeZone.autoupdatingCurrent.identifier
            ),
            end: CalendarEvent.EventDateTime(
                dateTime: now.addingTimeInterval(3600),
                date: nil,
                timeZone: TimeZone.autoupdatingCurrent.identifier
            ),
            attendees: [],
            createdBy: nil,
            calendarId: calendarId,
            location: nil,
            conference: nil
        )
    }

    func updateEvent(
        accessToken: String,
        calendarId: String,
        eventId: String,
        request: UpdateEventRequest
    ) async throws -> CalendarUpdateEventResponse {
        // Mock implementation - simulate an updated event with any provided fields
        let now = Date()
        let startEventTime: CalendarEvent.EventTime
        let endEventTime: CalendarEvent.EventTime
        
        if let start = request.start {
            switch start.type {
            case .timed:
                if let dateTime = start.dateTime {
                    startEventTime = .timed(dateTime: dateTime, timeZone: start.timeZone ?? request.timezone)
                } else {
                    startEventTime = .timed(dateTime: now, timeZone: request.timezone)
                }
            case .allDay:
                if let date = start.date {
                    startEventTime = .allDay(date: date)
                } else {
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd"
                    formatter.timeZone = TimeZone(secondsFromGMT: 0)
                    startEventTime = .allDay(date: formatter.string(from: Date()))
                }
            }
        } else {
            startEventTime = .timed(dateTime: now, timeZone: request.timezone)
        }
        
        if let end = request.end {
            switch end.type {
            case .timed:
                if let dateTime = end.dateTime {
                    endEventTime = .timed(dateTime: dateTime, timeZone: end.timeZone ?? request.timezone)
                } else {
                    endEventTime = .timed(dateTime: now.addingTimeInterval(3600), timeZone: request.timezone)
                }
            case .allDay:
                if let date = end.date {
                    endEventTime = .allDay(date: date)
                } else {
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd"
                    formatter.timeZone = TimeZone(secondsFromGMT: 0)
                    endEventTime = .allDay(date: formatter.string(from: Date().addingTimeInterval(86400)))
                }
            }
        } else {
            endEventTime = .timed(dateTime: now.addingTimeInterval(3600), timeZone: request.timezone)
        }

        let mockEvent = CalendarEvent(
            id: eventId,
            title: request.summary ?? "Updated Mock Event",
            description: request.description,
            start: CalendarEvent.EventDateTime(eventTime: startEventTime),
            end: CalendarEvent.EventDateTime(eventTime: endEventTime),
            attendees: [],
            createdBy: nil,
            calendarId: calendarId,
            location: request.location,
            conference: nil
        )

        return CalendarUpdateEventResponse(event: mockEvent)
    }
}

private final class MockSessionProvider: AuthSessionProviding {
    var session: OTPSession? {
        mockSession
    }

    private let mockSession: OTPSession

    init(session: OTPSession) {
        self.mockSession = session
    }
}

