//
//  AgentActionService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

protocol AgentActionServicing {
    func performAgentAction(request: AgentActionRequest, accessToken: String) async throws -> AgentActionResult
}

struct AgentActionService: AgentActionServicing {
    enum ServiceError: Error {
        case invalidURL
        case unexpectedResponse
        case decodingFailed(underlying: Error)
    }

    func performAgentAction(request: AgentActionRequest, accessToken: String) async throws -> AgentActionResult {
        let baseURL = AppConfiguration.agentBaseURL
        guard let endpoint = URL(string: "/api/v1/agent/action", relativeTo: baseURL) else {
            throw ServiceError.invalidURL
        }

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let requestBody = ["query": request.query]
        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(requestBody)

        // Log network call start
        let networkCallStart = Date()
        await TimingLogger.shared.logStart("frontend.agent_action_service.network_call", details: "query_length=\(request.query.count) chars")
        
        let (data, response) = try await NetworkSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ServiceError.unexpectedResponse
        }

        let statusCode = httpResponse.statusCode
        
        // Log network call completion (after we have status code)
        let networkCallDuration = Date().timeIntervalSince(networkCallStart)
        await TimingLogger.shared.logStep("frontend.agent_action_service.network_call", duration: networkCallDuration, details: "status_code=\(statusCode)")
        guard 200..<300 ~= statusCode else {
            // Extract error message from response body
            // FastAPI returns JSON with "detail" field for HTTPException
            let message: String
            if let jsonData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = jsonData["detail"] as? String {
                message = detail
            } else if let errorText = String(data: data, encoding: .utf8), !errorText.isEmpty {
                message = errorText
            } else {
                message = "Unknown error"
            }
            throw ServerError(statusCode: statusCode, message: message)
        }

        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let agentResponse = try decoder.decode(AgentResponse.self, from: data)

            return AgentActionResult(statusCode: statusCode, data: data, agentResponse: agentResponse)
        } catch {
            throw ServiceError.decodingFailed(underlying: error)
        }
    }
}

