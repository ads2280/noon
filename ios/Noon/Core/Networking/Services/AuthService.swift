//
//  AuthService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import Foundation
import os

private let authLogger = Logger(subsystem: "com.noon.app", category: "AuthService")

protocol AuthServicing {
    func requestOTP(phone: String) async throws -> OTPInitResponse
    func verifyOTP(phone: String, code: String) async throws -> OTPVerifyResponse
    func refreshSession(refreshToken: String) async throws -> OTPVerifyResponse
}

final class AuthService: AuthServicing {
    private let baseURL: URL
    private let urlSession: URLSession

    init(baseURL: URL = AuthService.defaultBaseURL(), urlSession: URLSession = NetworkSession.shared) {
        self.baseURL = baseURL
        self.urlSession = urlSession
    }

    func requestOTP(phone: String) async throws -> OTPInitResponse {
        let request = try makeRequest(path: "/api/v1/auth/otp", payload: ["phone": phone])
        return try await perform(request, decoding: OTPInitResponse.self)
    }

    func verifyOTP(phone: String, code: String) async throws -> OTPVerifyResponse {
        let request = try makeRequest(path: "/api/v1/auth/verify", payload: ["phone": phone, "code": code])
        return try await perform(request, decoding: OTPVerifyResponse.self)
    }

    func refreshSession(refreshToken: String) async throws -> OTPVerifyResponse {
        let request = try makeRequest(path: "/api/v1/auth/refresh", payload: ["refresh_token": refreshToken])
        return try await perform(request, decoding: OTPVerifyResponse.self)
    }
}

private extension AuthService {
    func makeRequest(path: String, payload: [String: String]) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw AuthServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])

        if let body = request.httpBody, let bodyString = String(data: body, encoding: .utf8) {
            authLogger.debug("➡️ Sending request to \(request.url?.absoluteString ?? "<unknown>") with body: \(bodyString, privacy: .private)")
        } else {
            authLogger.debug("➡️ Sending request to \(request.url?.absoluteString ?? "<unknown>") with empty body")
        }

        return request
    }

    func perform<Response: Decodable>(_ request: URLRequest, decoding type: Response.Type) async throws -> Response {
        do {
            let (data, response) = try await urlSession.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                authLogger.error("❌ Non-HTTP response for \(request.url?.absoluteString ?? "<unknown>")")
                throw AuthServiceError.http(-1)
            }
            authLogger.debug("⬅️ Response status \(httpResponse.statusCode) from \(httpResponse.url?.absoluteString ?? "<unknown>")")
            guard 200..<300 ~= httpResponse.statusCode else {
                if let payload = String(data: data, encoding: .utf8) {
                    authLogger.error("❌ Server returned status \(httpResponse.statusCode) with body: \(payload, privacy: .private)")
                }
                throw AuthServiceError.http(httpResponse.statusCode)
            }

            do {
                let decoded = try JSONDecoder().decode(type, from: data)
                authLogger.debug("✅ Successfully decoded \(String(describing: type)) for \(httpResponse.url?.absoluteString ?? "<unknown>")")
                return decoded
            } catch {
                authLogger.error("❌ Decoding error for \(httpResponse.url?.absoluteString ?? "<unknown>"): \(String(describing: error))")
                throw AuthServiceError.decoding(error)
            }
        } catch {
            if let authError = error as? AuthServiceError {
                throw authError
            }
            authLogger.error("❌ Network error for \(request.url?.absoluteString ?? "<unknown>"): \(String(describing: error))")
            throw AuthServiceError.network(error)
        }
    }

    static func defaultBaseURL() -> URL {
        if let override = ProcessInfo.processInfo.environment["BACKEND_URL"], let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}

