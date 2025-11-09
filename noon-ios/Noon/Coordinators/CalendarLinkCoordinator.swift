//
//  CalendarLinkCoordinator.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Combine
import AuthenticationServices
import UIKit

protocol CalendarOAuthCoordinating {
    @MainActor
    func startAuthorization(with start: GoogleOAuthStart, callbackScheme: String) async throws -> URL
}

enum CalendarLinkError: Error {
    case failedToStart
    case missingCallbackURL
    case userCancelled
    case stateMismatch
    case missingResult
    case resultError(message: String?)
    case underlying(Error)
}

@MainActor
final class CalendarLinkCoordinator: NSObject, ObservableObject, CalendarOAuthCoordinating {
    private var session: ASWebAuthenticationSession?
    private let anchorProvider: @MainActor @Sendable () -> ASPresentationAnchor

    init(anchorProvider: @escaping @MainActor @Sendable () -> ASPresentationAnchor = CalendarLinkCoordinator.defaultPresentationAnchor) {
        self.anchorProvider = anchorProvider
    }

    func startAuthorization(with start: GoogleOAuthStart, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: start.authorizationURL,
                callbackURLScheme: callbackScheme
            ) { [weak self] callbackURL, error in
                self?.session = nil

                if let specificError = error as? ASWebAuthenticationSessionError, specificError.code == .canceledLogin {
                    continuation.resume(throwing: CalendarLinkError.userCancelled)
                    return
                }

                if let error {
                    continuation.resume(throwing: CalendarLinkError.underlying(error))
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

            self.session = session

            if session.start() == false {
                self.session = nil
                continuation.resume(throwing: CalendarLinkError.failedToStart)
            }
        }
    }
}

extension CalendarLinkCoordinator: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        anchorProvider()
    }
}

private extension CalendarLinkCoordinator {
    static func defaultPresentationAnchor() -> ASPresentationAnchor {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }

        guard let windowScene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first else {
            if #available(iOS 26.0, *) {
                preconditionFailure("Unable to locate a UIWindowScene for CalendarLinkCoordinator presentation.")
            } else {
                return UIWindow(frame: .zero)
            }
        }

        if let window = windowScene.windows.first(where: { $0.isKeyWindow }) {
            return window
        }

        if #available(iOS 26.0, *) {
            return UIWindow(windowScene: windowScene)
        } else {
            let window = UIWindow(frame: windowScene.coordinateSpace.bounds)
            window.windowScene = windowScene
            return window
        }
    }
}

