//
//  AuthViewModel.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import Foundation
import Combine
import os

@MainActor
protocol AuthSessionProviding: AnyObject {
    var session: OTPSession? { get }
    func refreshSession() async throws -> StoredAuthSession
}

@MainActor
final class AuthViewModel: ObservableObject {
    enum Phase {
        case enterPhone
        case enterCode
        case authenticated
    }

    enum SessionError: Error {
        case missingRefreshToken
    }

    private let logger = Logger(subsystem: "com.noon.app", category: "AuthViewModel")

    @Published private(set) var phase: Phase = .enterPhone
    @Published private(set) var isLoading: Bool = false
    @Published var phoneNumber: String = ""
    @Published var otpCode: String = ""
    @Published private(set) var errorMessage: String?
    @Published private(set) var session: OTPSession?
    @Published private(set) var user: UserProfile?
    @Published private(set) var storedSession: StoredAuthSession?

    private let authService: AuthServicing
    private let persistence: AuthPersistence

    init(authService: AuthServicing? = nil, persistence: AuthPersistence? = nil) {
        self.authService = authService ?? AuthService()
        self.persistence = persistence ?? AuthPersistence.shared

        if let stored = self.persistence.loadSession() {
            self.session = stored.session
            self.user = stored.user
            self.storedSession = stored
            self.phase = .authenticated
            logger.debug("🔁 Restored persisted session for user \(stored.user.id, privacy: .private)")
        }
    }

    func requestOTP() async {
        let trimmed = self.phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let normalized = normalizePhoneNumber(trimmed) else {
            self.errorMessage = "Enter a valid phone number."
            logger.error("❌ Attempted to request OTP with invalid phone number")
            return
        }

        logger.debug("📨 Requesting OTP for phone \(normalized, privacy: .private)")
        await perform {
            _ = try await self.authService.requestOTP(phone: normalized)
            self.phase = .enterCode
            self.errorMessage = nil
            self.logger.debug("✅ OTP requested successfully for phone \(normalized, privacy: .private)")
        }
    }

    func verifyOTP() async {
        let trimmedCode = self.otpCode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedCode.isEmpty == false else {
            self.errorMessage = "Enter the code you received."
            logger.error("❌ Attempted to verify OTP with empty code")
            return
        }

        let normalizedPhone = normalizePhoneNumber(self.phoneNumber) ?? self.phoneNumber

        logger.debug("🔐 Verifying OTP for phone \(normalizedPhone, privacy: .private)")
        await perform {
            let response = try await self.authService.verifyOTP(phone: normalizedPhone, code: trimmedCode)
            self.storeSession(response)
            self.phase = .authenticated
            self.errorMessage = nil
            self.logger.debug("🎉 OTP verification succeeded for user \(response.user.id, privacy: .private)")
        }
    }

    func refreshSession() async throws -> StoredAuthSession {
        guard let refreshToken = self.session?.refreshToken ?? self.storedSession?.session.refreshToken else {
            logger.error("❌ Attempted to refresh session without a refresh token")
            throw SessionError.missingRefreshToken
        }

        let currentUserID = self.user?.id ?? "<unknown>"
        logger.debug("🔄 Refreshing auth session for user \(currentUserID, privacy: .private)")
        let response = try await self.authService.refreshSession(refreshToken: refreshToken)
        self.storeSession(response)
        self.phase = .authenticated
        logger.debug("✅ Successfully refreshed auth session for user \(response.user.id, privacy: .private)")
        return StoredAuthSession(session: response.session, user: response.user)
    }

    func signOut() {
        logger.debug("🚪 Signing out current user")
        self.phoneNumber = ""
        self.otpCode = ""
        self.session = nil
        self.user = nil
        self.storedSession = nil
        self.phase = .enterPhone
        self.persistence.clear()
    }

    func clearError() {
        self.errorMessage = nil
    }
}

private extension AuthViewModel {
    func normalizePhoneNumber(_ input: String) -> String? {
        let digits = input.filter(\.isNumber)
        guard digits.isEmpty == false else { return nil }

        if digits.count == 10 {
            return "+1\(digits)"
        }

        if digits.count == 11, digits.first == "1" {
            return "+\(digits)"
        }

        if input.hasPrefix("+"), digits.count >= 10 {
            return "+\(digits)"
        }

        return nil
    }

    func perform(_ work: @escaping () async throws -> Void) async {
        self.isLoading = true
        defer { self.isLoading = false }

        do {
            try await work()
        } catch let error as AuthServiceError {
            switch error {
            case .http(let statusCode):
                self.errorMessage = "Request failed with status \(statusCode)."
                logger.error("❌ HTTP error \(statusCode) during auth flow")
            case .decoding:
                self.errorMessage = "Received unexpected response from server."
                logger.error("❌ Decoding error during auth flow: \(String(describing: error))")
            case .network(let underlying):
                self.errorMessage = "Network error: \(underlying.localizedDescription)"
                logger.error("❌ Network error during auth flow: \(underlying.localizedDescription, privacy: .public)")
            case .invalidURL:
                self.errorMessage = "Invalid server URL."
                logger.error("❌ Invalid URL configured for auth service")
            }
        } catch {
            self.errorMessage = "Something went wrong. Please try again."
            logger.error("❌ Unexpected error during auth flow: \(String(describing: error))")
        }
    }

    func storeSession(_ response: OTPVerifyResponse) {
        let stored = StoredAuthSession(session: response.session, user: response.user)
        self.session = response.session
        self.user = response.user
        self.storedSession = stored
        self.persistence.save(response)
    }
}

// MARK: - Persistence

struct StoredAuthSession: Codable {
    let session: OTPSession
    let user: UserProfile
}

final class AuthPersistence {
    static let shared = AuthPersistence()

    private let sessionKey = "noon.auth.session"
    private let userDefaults: UserDefaults

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func save(_ response: OTPVerifyResponse) {
        let stored = StoredAuthSession(session: response.session, user: response.user)
        do {
            let data = try JSONEncoder().encode(stored)
            self.userDefaults.set(data, forKey: sessionKey)
        } catch {
            #if DEBUG
            print("Failed to save auth session: \(error)")
            #endif
        }
    }

    func loadSession() -> StoredAuthSession? {
        guard let data = self.userDefaults.data(forKey: sessionKey) else { return nil }
        do {
            return try JSONDecoder().decode(StoredAuthSession.self, from: data)
        } catch {
            #if DEBUG
            print("Failed to load auth session: \(error)")
            #endif
            return nil
        }
    }

    func clear() {
        self.userDefaults.removeObject(forKey: sessionKey)
    }
}

extension AuthViewModel: AuthSessionProviding {}

