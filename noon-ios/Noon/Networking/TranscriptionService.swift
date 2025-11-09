//
//  TranscriptionService.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/9/25.
//

import Foundation

struct TranscriptionResponseDTO: Decodable {
    let text: String
}

struct TranscriptionResult {
    let text: String
    let statusCode: Int
}

protocol TranscriptionServicing {
    func transcribeAudio(at fileURL: URL) async throws -> TranscriptionResult
}

struct TranscriptionService: TranscriptionServicing {
    enum ServiceError: Error {
        case invalidURL
        case unexpectedResponse
    }

    var baseURL: URL = URL(string: "http://localhost:8001")!

    func transcribeAudio(at fileURL: URL) async throws -> TranscriptionResult {
        let endpoint = baseURL.appendingPathComponent("/v1/transcriptions")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let bodyData = try buildMultipartBody(fileURL: fileURL, boundary: boundary)
        request.httpBody = bodyData

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              200..<300 ~= httpResponse.statusCode else {
            if let serverMessage = String(data: data, encoding: .utf8), !serverMessage.isEmpty {
                throw ServerError(statusCode: (response as? HTTPURLResponse)?.statusCode ?? -1, message: serverMessage)
            }
            throw ServiceError.unexpectedResponse
        }

        if let jsonString = String(data: data, encoding: .utf8) {
            print("[Agent] Raw transcription payload: \(jsonString)")
        } else {
            print("[Agent] Received transcription payload (non-UTF8, \(data.count) bytes)")
        }

        let decoder = JSONDecoder()
        let dto = try decoder.decode(TranscriptionResponseDTO.self, from: data)
        return TranscriptionResult(text: dto.text, statusCode: httpResponse.statusCode)
    }
}

private extension TranscriptionService {
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

struct ServerError: Error {
    let statusCode: Int
    let message: String
}

