//
//  AppConfiguration.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Combine
import Foundation

enum AppConfiguration {
    private static func infoValue(for key: String) -> String? {
        Bundle.main.object(forInfoDictionaryKey: key) as? String
    }

    private static func environmentValue(for key: String) -> String? {
        ProcessInfo.processInfo.environment[key]
    }

    /// Full OAuth callback URL (e.g. noon://oauth/google).
    static var googleOAuthCallbackURL: URL {
        guard let string = infoValue(for: "GoogleOAuthCallbackURL") ?? environmentValue(for: "GOOGLE_OAUTH_CALLBACK_URL"),
              let url = URL(string: string) else {
            fatalError("GoogleOAuthCallbackURL must be set in Info.plist or GOOGLE_OAUTH_CALLBACK_URL environment variable")
        }
        return url
    }

    /// Callback URL scheme used by ASWebAuthenticationSession.
    static var googleOAuthCallbackScheme: String {
        googleOAuthCallbackURL.scheme ?? "noon"
    }

    /// Base URL for calling the Noon agent endpoint.
    static var agentBaseURL: URL {
        if let value = infoValue(for: "AgentBaseURL") ?? environmentValue(for: "AGENT_BASE_URL"),
           let url = URL(string: value) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
    
    /// Supabase project URL
    static var supabaseURL: String {
        infoValue(for: "SupabaseURL") ?? environmentValue(for: "SUPABASE_URL") ?? "https://YOUR_PROJECT_ID.supabase.co"
    }
    
    /// Supabase anonymous/public key
    static var supabaseAnonKey: String {
        infoValue(for: "SupabaseAnonKey") ?? environmentValue(for: "SUPABASE_ANON_KEY") ?? ""
    }
}
