//
//  AppConfiguration.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

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
}

