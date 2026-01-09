//
//  AgentActionModels.swift
//  Noon
//
//  Created by Auto on 11/12/25.
//

import Foundation

struct AgentActionResult {
    let statusCode: Int
    let data: Data
    let agentResponse: AgentResponse

    var responseString: String? {
        String(data: data, encoding: .utf8)
    }
}

struct ServerError: Error {
    let statusCode: Int
    let message: String
}
