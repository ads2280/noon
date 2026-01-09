//
//  AuthViewModel.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import Foundation
import Combine
import os
import Supabase

@MainActor
protocol AuthSessionProviding: AnyObject {
    var session: OTPSession? { get }
    // refreshSession() removed - Supabase handles automatic refresh
}

@MainActor
final class AuthViewModel: ObservableObject {
    enum Phase {
        case enterPhone
        case enterCode
        case authenticated
    }


    private let logger = Logger(subsystem: "com.noon.app", category: "AuthViewModel")

    @Published private(set) var phase: Phase = .enterPhone
    @Published private(set) var isLoading: Bool = false
    @Published var phoneNumber: String = ""
    @Published var otpCode: String = ""
    @Published private(set) var errorMessage: String?
    @Published private(set) var session: OTPSession?
    @Published private(set) var user: UserProfile?

    private let authService: AuthServicing

    init(authService: AuthServicing? = nil) {
        self.authService = authService ?? AuthService()
        
        // Check Supabase client for existing session asynchronously
        // We can't do async work in init, so we'll check on first access via the session property
        // The session property will handle async session retrieval
    }
    
    /// Restore session from Supabase on app launch
    func restoreSessionIfNeeded() async {
        do {
            let supabaseSession = try await AuthTokenProvider.shared.client.auth.session
            // Restore session from Supabase
            self.session = OTPSession(
                accessToken: supabaseSession.accessToken,
                refreshToken: supabaseSession.refreshToken,
                tokenType: supabaseSession.tokenType,
                expiresIn: Int(supabaseSession.expiresIn)
            )
            // Note: We don't have user info from Supabase session alone, but that's okay
            // The session is valid and will be used for API calls
            self.phase = .authenticated
            logger.debug("🔁 Restored Supabase session")
        } catch {
            // No existing session, user needs to sign in
            logger.debug("No existing Supabase session found")
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
            
            // Set session in Supabase client (handles Keychain storage and auto-refresh)
            // We create a minimal session from tokens received from our backend
            // Supabase will handle automatic refresh using the refresh token
            guard let refreshToken = response.session.refreshToken else {
                throw AuthServiceError.network(NSError(domain: "AuthError", code: -1, userInfo: [NSLocalizedDescriptionKey: "No refresh token received"]))
            }
            
            // Set session in Supabase client using accessToken and refreshToken directly
            // Supabase will handle creating the Session object internally and storing it securely
            try await AuthTokenProvider.shared.client.auth.setSession(
                accessToken: response.session.accessToken,
                refreshToken: refreshToken
            )
            
            self.storeSession(response)
            self.phase = .authenticated
            self.errorMessage = nil
            self.logger.debug("🎉 OTP verification succeeded for user \(response.user.id, privacy: .private)")
        }
    }

    func signOut() {
        logger.debug("🚪 Signing out current user")
        Task {
            try? await AuthTokenProvider.shared.client.auth.signOut()
        }
        self.phoneNumber = ""
        self.otpCode = ""
        self.session = nil
        self.user = nil
        self.phase = .enterPhone
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
        self.session = response.session
        self.user = response.user
        // Session is already stored in Supabase client (Keychain) via setSession call
    }
}

extension AuthViewModel: AuthSessionProviding {
    // The session property is already declared as @Published private(set) var session: OTPSession?
    // This satisfies the protocol requirement, so no additional implementation is needed
}











