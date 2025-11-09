//
//  CalendarsView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import SwiftUI

struct CalendarsView: View {
    @StateObject private var viewModel: CalendarsViewModel
    @StateObject private var coordinator = CalendarLinkCoordinator()

    init(authViewModel: AuthViewModel, calendarService: CalendarServicing? = nil) {
        self.init(sessionProvider: authViewModel, calendarService: calendarService)
    }

    init(sessionProvider: AuthSessionProviding, calendarService: CalendarServicing? = nil) {
        _viewModel = StateObject(
            wrappedValue: CalendarsViewModel(
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

private extension CalendarsView {
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
        if let message = viewModel.errorMessage {
            errorState(message: message)
        } else if viewModel.accounts.isEmpty {
            if viewModel.isLoading {
                EmptyView()
            } else {
            emptyState
            }
        } else {
            accountsList
        }

        connectInlineButton
            .padding(.top, 4)
    }
    func errorState(message: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Unable to load calendars", systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(ColorPalette.Semantic.warning)
                .font(.headline)
            Text(message)
                .foregroundStyle(ColorPalette.Text.secondary)
            Button("Retry") {
                Task {
                    await viewModel.loadCalendars(force: true)
                }
            }
            .foregroundStyle(ColorPalette.Semantic.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(ColorPalette.Surface.elevated.opacity(0.6))
        )
    }

    var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "calendar.badge.exclamationmark")
                .imageScale(.large)
                .foregroundStyle(ColorPalette.Semantic.secondary)
            Text("No calendar accounts connected yet")
                .font(.headline)
                .foregroundStyle(ColorPalette.Text.primary)
            Text("Connect a calendar account to get started.")
                .font(.subheadline)
                .foregroundStyle(ColorPalette.Text.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 48)
    }

    var accountsList: some View {
        VStack(spacing: 12) {
            ForEach(viewModel.accounts, id: \.self) { account in
                accountRow(account)
            }
        }
    }

    func accountRow(_ account: GoogleAccount) -> some View {
        HStack(spacing: 16) {
            Text(account.email)
                .font(.headline)
                .foregroundStyle(ColorPalette.Text.primary)
                .lineLimit(1)
                .truncationMode(.middle)

            Spacer()

            if viewModel.isDeleting(account) {
                ProgressView()
                    .progressViewStyle(.circular)
                    .tint(ColorPalette.Text.secondary)
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
            }
        }
        .padding(.vertical, 18)
        .padding(.horizontal, 20)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(ColorPalette.Surface.elevated.opacity(0.85))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(ColorPalette.Surface.overlay.opacity(0.4), lineWidth: 1)
        )
    }

    func successBanner(_ message: String) -> some View { EmptyView() }

    func errorBanner(_ message: String) -> some View { EmptyView() }
}

#Preview {
    let session = OTPSession(accessToken: "token", refreshToken: "refresh", tokenType: "bearer", expiresIn: 3600)
    let user = UserProfile(id: UUID().uuidString, phone: "+15551234567")
    let sessionProvider = MockSessionProvider(stored: StoredAuthSession(session: session, user: user))
    return NavigationStack {
        CalendarsView(sessionProvider: sessionProvider, calendarService: MockCalendarService())
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
}

private final class MockSessionProvider: AuthSessionProviding {
    var session: OTPSession? {
        stored.session
    }

    private let stored: StoredAuthSession

    init(stored: StoredAuthSession) {
        self.stored = stored
    }

    func refreshSession() async throws -> StoredAuthSession {
        throw AuthViewModel.SessionError.missingRefreshToken
    }
}

