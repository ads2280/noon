//
//  AuthTokenProvider.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import Supabase
import Foundation
import os

private let tokenLogger = Logger(subsystem: "com.noon.app", category: "AuthTokenProvider")

@MainActor
final class AuthTokenProvider {
    static let shared = AuthTokenProvider()
    
    private let supabaseClient: SupabaseClient
    
    private init() {
        let urlString = AppConfiguration.supabaseURL
        guard let url = URL(string: urlString) else {
            fatalError("Invalid Supabase URL: \(urlString)")
        }
        let key = AppConfiguration.supabaseAnonKey
        
        // Configure AuthClient to use new behavior (emit local session as initial session)
        // This eliminates the warning and ensures sessions are emitted immediately
        let authOptions = SupabaseClientOptions.AuthOptions(
            emitLocalSessionAsInitialSession: true
        )
        let defaultOptions = SupabaseClientOptions()
        let options = SupabaseClientOptions(
            db: defaultOptions.db,
            auth: authOptions,
            global: defaultOptions.global,
            functions: defaultOptions.functions,
            realtime: defaultOptions.realtime,
            storage: defaultOptions.storage
        )
        
        self.supabaseClient = SupabaseClient(
            supabaseURL: url,
            supabaseKey: key,
            options: options
        )
    }
    
    /// Returns the current access token from Supabase session (always fresh, auto-refreshed)
    /// Returns nil if no session exists or if there's an error
    /// This method ensures the token is not expired by refreshing it if necessary
    func currentAccessToken() async -> String? {
        do {
            var session = try await supabaseClient.auth.session
            
            // Check if token is expired or expiring soon (within 5 minutes for safety)
            let now = Date().timeIntervalSince1970
            let expiresAt = session.expiresAt
            let buffer: TimeInterval = 300 // Refresh if expiring within 5 minutes (more aggressive)
            let timeUntilExpiry = expiresAt - now
            
            // Always refresh if expired or expiring soon
            if expiresAt <= (now + buffer) {
                // Token is expired or expiring soon, refresh it
                if timeUntilExpiry <= 0 {
                    tokenLogger.debug("🔄 Token is expired (expired \(Int(-timeUntilExpiry))s ago), refreshing...")
                } else {
                    tokenLogger.debug("🔄 Token expires in \(Int(timeUntilExpiry))s, refreshing proactively...")
                }
                
                do {
                    session = try await supabaseClient.auth.refreshSession()
                    let newExpiresAt = session.expiresAt
                    let newTimeUntilExpiry = newExpiresAt - Date().timeIntervalSince1970
                    tokenLogger.debug("✅ Token refreshed successfully, new expiry in \(Int(newTimeUntilExpiry))s")
                } catch {
                    tokenLogger.error("❌ Failed to refresh token: \(String(describing: error))")
                    // If refresh fails, don't return the expired token
                    // Return nil so the app can handle re-authentication
                    return nil
                }
            } else {
                tokenLogger.debug("✅ Token is valid for \(Int(timeUntilExpiry))s")
            }
            
            // Final safety check: Never return an expired token
            let finalCheck = Date().timeIntervalSince1970
            if session.expiresAt <= finalCheck {
                tokenLogger.error("❌ Token is expired (expired \(Int(finalCheck - session.expiresAt))s ago) even after refresh attempt")
                return nil
            }
            
            return session.accessToken
        } catch {
            tokenLogger.error("❌ Failed to get session: \(String(describing: error))")
            return nil
        }
    }
    
    /// Returns the Supabase client (for setting sessions)
    var client: SupabaseClient {
        supabaseClient
    }
    
    /// Check if user is authenticated
    func isAuthenticated() async -> Bool {
        do {
            _ = try await supabaseClient.auth.session
            return true
        } catch {
            return false
        }
    }
}
