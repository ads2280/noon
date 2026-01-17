//
//  CalendarAccountsViewModel.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Combine
import Foundation

@MainActor
final class CalendarAccountsViewModel: ObservableObject {
    @Published private(set) var accounts: [GoogleAccount] = []
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var errorMessage: String?
    @Published private(set) var isLinking: Bool = false
    @Published private(set) var linkingMessage: String?
    @Published private(set) var linkingError: String?
    @Published private(set) var deletingAccountIDs: Set<String> = []
    @Published private(set) var deletionError: String?
    @Published var expandedAccountIDs: Set<String> = []

    private let calendarService: CalendarServicing
    private let callbackScheme: String
    private var hasLoaded: Bool = false
    private let sessionProvider: AuthSessionProviding?
    private let storedSession: OTPSession?

    init(session: OTPSession, calendarService: CalendarServicing? = nil, callbackScheme: String? = nil) {
        self.calendarService = calendarService ?? CalendarService()
        self.callbackScheme = callbackScheme ?? AppConfiguration.googleOAuthCallbackScheme
        self.sessionProvider = nil
        self.storedSession = session
    }

    init(sessionProvider: AuthSessionProviding, calendarService: CalendarServicing? = nil, callbackScheme: String? = nil) {
        self.calendarService = calendarService ?? CalendarService()
        self.callbackScheme = callbackScheme ?? AppConfiguration.googleOAuthCallbackScheme
        self.sessionProvider = sessionProvider
        self.storedSession = sessionProvider.session
    }

    func loadCalendars(force: Bool = false) async {
        guard !isLoading else { return }
        if hasLoaded && !force {
            return
        }

        isLoading = true
        defer { isLoading = false }

        guard let accessToken = await currentAccessToken() else {
            errorMessage = "We couldn't load your calendars because your session is unavailable."
            return
        }

        do {
            // Refresh calendars from Google API on first load or when forced
            // This ensures calendar metadata is up-to-date in Supabase
            if !hasLoaded || force {
                try await calendarService.refreshCalendars(accessToken: accessToken)
            }
            
            // Fetch calendars from Supabase (now up-to-date after refresh)
            let fetched = try await calendarService.fetchCalendars(accessToken: accessToken)
            accounts = fetched
            errorMessage = nil
            hasLoaded = true
        } catch let serviceError as CalendarServiceError {
            switch serviceError {
            case .unauthorized:
                // Supabase should auto-refresh, but if we still get 401, session is invalid
                errorMessage = "We couldn't access your calendars. Please sign in again."
            default:
                errorMessage = "We couldn't load your calendars. Please try again later."
            }
        } catch {
            errorMessage = "We couldn't load your calendars. Please try again later."
        }
    }

    func linkCalendar(using coordinator: CalendarOAuthCoordinating) async {
        guard isLinking == false else { return }

        isLinking = true
        linkingError = nil
        linkingMessage = nil

        guard let accessToken = await currentAccessToken() else {
            linkingError = "You're signed out. Please sign in again."
            isLinking = false
            return
        }

        do {
            let start = try await calendarService.beginGoogleOAuth(accessToken: accessToken)
            let callbackURL = try await coordinator.startAuthorization(with: start, callbackScheme: callbackScheme)
            let outcome = try evaluateCallbackURL(callbackURL, expectedState: start.state)

            switch outcome {
            case .success(let message):
                linkingMessage = message ?? "Google Calendar linked."
                await loadCalendars(force: true)
            case .failure(let message):
                linkingError = message
            }
        } catch let serviceError as CalendarServiceError {
            switch serviceError {
            case .unauthorized:
                // Supabase should auto-refresh, but if we still get 401, session is invalid
                linkingError = "We couldn't access your account. Please sign in again."
            default:
                linkingError = "We couldn't start the Google sign-in flow. Please try again."
            }
        } catch let linkError as CalendarLinkError {
            switch linkError {
            case .userCancelled:
                linkingError = "Google sign-in was cancelled."
            case .stateMismatch:
                linkingError = "Security validation failed. Please try again."
            case .resultError(let message):
                linkingError = message ?? "Google reported an error while linking your calendar."
            case .missingResult, .missingCallbackURL:
                linkingError = "We couldn't read Google's response. Please try again."
            case .failedToStart:
                linkingError = "Unable to open the Google sign-in flow."
            case .underlying(let error):
                if (error as NSError).code == NSUserCancelledError {
                    linkingError = "Google sign-in was cancelled."
                } else {
                    linkingError = "Something went wrong while linking your calendar."
                }
            }
        } catch {
            linkingError = "Something went wrong while linking your calendar."
        }

        isLinking = false
    }

    func clearLinkingFeedback() {
        linkingError = nil
        linkingMessage = nil
    }

    func deleteAccount(_ account: GoogleAccount) async {
        guard deletingAccountIDs.contains(account.id) == false else { return }

        deletingAccountIDs.insert(account.id)
        defer { deletingAccountIDs.remove(account.id) }

        guard let accessToken = await currentAccessToken() else {
            deletionError = "You're signed out. Please sign in again."
            return
        }

        do {
            try await calendarService.deleteCalendar(accessToken: accessToken, accountId: account.id)
            accounts.removeAll { $0.id == account.id }
            deletionError = nil
        } catch let serviceError as CalendarServiceError {
            switch serviceError {
            case .unauthorized:
                // Supabase should auto-refresh, but if we still get 401, session is invalid
                deletionError = "We couldn't access your account. Please sign in again."
            default:
                deletionError = "We couldn't remove that account. Please try again."
            }
        } catch {
            deletionError = "We couldn't remove that account. Please try again."
        }
    }

    func isDeleting(_ account: GoogleAccount) -> Bool {
        deletingAccountIDs.contains(account.id)
    }

    func clearDeletionError() {
        deletionError = nil
    }

    func toggleExpansion(for accountID: String) {
        if expandedAccountIDs.contains(accountID) {
            expandedAccountIDs.remove(accountID)
        } else {
            expandedAccountIDs.insert(accountID)
        }
    }

    func isExpanded(_ account: GoogleAccount) -> Bool {
        expandedAccountIDs.contains(account.id)
    }

    private func currentAccessToken() async -> String? {
        // Always use AuthTokenProvider - single source of truth, always fresh
        return await AuthTokenProvider.shared.currentAccessToken()
    }

    private enum OAuthCallbackOutcome {
        case success(message: String?)
        case failure(message: String)
    }

    private func evaluateCallbackURL(_ url: URL, expectedState: String) throws -> OAuthCallbackOutcome {
        guard url.scheme?.caseInsensitiveCompare(callbackScheme) == .orderedSame else {
            throw CalendarLinkError.missingResult
        }

        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            throw CalendarLinkError.missingResult
        }

        let queryItems = components.queryItems ?? []
        var payload: [String: String] = [:]
        for item in queryItems {
            if let value = item.value {
                payload[item.name] = value
            }
        }

        guard let returnedState = payload["state"], returnedState == expectedState else {
            throw CalendarLinkError.stateMismatch
        }

        guard let result = payload["result"] else {
            throw CalendarLinkError.missingResult
        }

        if result.lowercased() == "success" {
            return .success(message: payload["message"])
        }

        if result.lowercased() == "error" {
            throw CalendarLinkError.resultError(message: payload["message"])
        }

        throw CalendarLinkError.missingResult
    }
}

