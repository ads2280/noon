//
//  TranscriptionService.swift
//  Noon
//
//  Created by Auto on 12/19/25.
//

import Foundation

protocol TranscriptionServicing {
    func transcribe(request: TranscriptionRequest, accessToken: String) async throws -> TranscriptionResult
}

struct TranscriptionService: TranscriptionServicing {
    enum ServiceError: Error {
        case invalidURL
        case unexpectedResponse
        case decodingFailed(underlying: Error)
    }

    func transcribe(request: TranscriptionRequest, accessToken: String) async throws -> TranscriptionResult {
        let baseURL = AppConfiguration.agentBaseURL
        guard let endpoint = URL(string: "/api/v1/agent/transcribe", relativeTo: baseURL) else {
            throw ServiceError.invalidURL
        }

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        let boundary = UUID().uuidString
        urlRequest.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let bodyData = try buildMultipartBody(request: request, boundary: boundary)
        urlRequest.httpBody = bodyData

        let (data, response) = try await NetworkSession.shared.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ServiceError.unexpectedResponse
        }

        let statusCode = httpResponse.statusCode
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
            let transcriptionResponse = try decoder.decode(TranscriptionResponse.self, from: data)

            return TranscriptionResult(statusCode: statusCode, text: transcriptionResponse.text)
        } catch {
            throw ServiceError.decodingFailed(underlying: error)
        }
    }
}

private extension TranscriptionService {
    func buildMultipartBody(request: TranscriptionRequest, boundary: String) throws -> Data {
        var body = Data()
        let fileData = try Data(contentsOf: request.fileURL)

        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(request.filename)\"\r\n")
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
