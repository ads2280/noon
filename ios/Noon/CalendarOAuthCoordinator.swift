//
//  CalendarOAuthCoordinator.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import AuthenticationServices
import Combine
import UIKit

protocol CalendarOAuthCoordinating: AnyObject {
    func startAuthorization(with start: GoogleOAuthStart, callbackScheme: String) async throws -> URL
}

enum CalendarLinkError: Error {
    case failedToStart
    case missingCallbackURL
    case missingResult
    case stateMismatch
    case resultError(message: String?)
    case userCancelled
    case underlying(Error)
}

@MainActor
final class CalendarOAuthCoordinator: NSObject, ObservableObject {
    private var currentSession: ASWebAuthenticationSession?
}

extension CalendarOAuthCoordinator: CalendarOAuthCoordinating {
    func startAuthorization(with start: GoogleOAuthStart, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            currentSession?.cancel()

            let session = ASWebAuthenticationSession(
                url: start.authorizationURL,
                callbackURLScheme: callbackScheme
            ) { [weak self] callbackURL, error in
                guard let self else { return }
                self.currentSession = nil

                if let error {
                    if let authError = error as? ASWebAuthenticationSessionError,
                       authError.code == .canceledLogin {
                        continuation.resume(throwing: CalendarLinkError.userCancelled)
                    } else {
                        continuation.resume(throwing: CalendarLinkError.underlying(error))
                    }
                    return
                }

                guard let callbackURL else {
                    continuation.resume(throwing: CalendarLinkError.missingCallbackURL)
                    return
                }

                continuation.resume(returning: callbackURL)
            }

            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = true

            guard session.start() else {
                continuation.resume(throwing: CalendarLinkError.failedToStart)
                return
            }

            self.currentSession = session
        }
    }
}

@MainActor
extension CalendarOAuthCoordinator: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        let windowScenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }

        guard let selectedScene = windowScenes.first(where: { $0.activationState == .foregroundActive }) ?? windowScenes.first else {
            if #available(iOS 26.0, *) {
                fatalError("No window scene is available to present ASWebAuthenticationSession.")
            } else {
                return UIWindow(frame: UIScreen.main.bounds)
            }
        }

        if let window = selectedScene.windows.first(where: { $0.isKeyWindow }) ?? selectedScene.windows.first {
            return window
        }

        if #available(iOS 26.0, *) {
            return ASPresentationAnchor(windowScene: selectedScene)
        } else {
            return UIWindow(frame: selectedScene.screen.bounds)
        }
    }
}


