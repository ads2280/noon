//
//  AgentActionService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

protocol AgentActionServicing {
    func performAgentAction(fileURL: URL, accessToken: String) async throws -> AgentActionResult
}

struct AgentActionService: AgentActionServicing {
    enum ServiceError: Error {
        case invalidURL
        case unexpectedResponse
        case decodingFailed(underlying: Error)
    }

    func performAgentAction(fileURL: URL, accessToken: String) async throws -> AgentActionResult {
        let baseURL = AppConfiguration.agentBaseURL
        guard let endpoint = URL(string: "/api/v1/agent/action", relativeTo: baseURL) else {
            throw ServiceError.invalidURL
        }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let bodyData = try buildMultipartBody(fileURL: fileURL, boundary: boundary)
        request.httpBody = bodyData

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ServiceError.unexpectedResponse
        }

        let statusCode = httpResponse.statusCode
        guard 200..<300 ~= statusCode else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw ServerError(statusCode: statusCode, message: message)
        }

        do {
            let decoder = JSONDecoder()
            let agentResponse = try decoder.decode(AgentResponse.self, from: data)

            return AgentActionResult(statusCode: statusCode, data: data, agentResponse: agentResponse)
        } catch {
            throw ServiceError.decodingFailed(underlying: error)
        }
    }
}

private extension AgentActionService {
    func buildMultipartBody(fileURL: URL, boundary: String) throws -> Data {
        var body = Data()
        let filename = fileURL.lastPathComponent.isEmpty ? "recording.wav" : fileURL.lastPathComponent
        let fileData = try Data(contentsOf: fileURL)

        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: audio/wav\r\n\r\n")
        body.append(fileData)
        body.append("\r\n")
        body.append("--\(boundary)--\r\n")

        return body
    }
}

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}

