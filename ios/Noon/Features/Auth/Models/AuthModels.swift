//
//  AuthModels.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import Foundation

struct OTPInitResponse: Decodable {
    let status: String
}

struct OTPSession: Codable {
    let accessToken: String
    let refreshToken: String?
    let tokenType: String
    let expiresIn: Int?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }
}

struct UserProfile: Codable {
    let id: String
    let phone: String?
}

struct OTPVerifyResponse: Codable {
    let session: OTPSession
    let user: UserProfile
}

enum AuthServiceError: Error {
    case invalidURL
    case network(Error)
    case http(Int)
    case decoding(Error)
}
