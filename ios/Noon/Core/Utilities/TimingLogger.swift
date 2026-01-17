//
//  TimingLogger.swift
//  Noon
//
//  Created for performance debugging
//  Only logs in DEBUG builds or when ENABLE_TIMING_LOGGER environment variable is set
//

import Foundation

#if DEBUG
private nonisolated let isDebugBuild = true
#else
private nonisolated let isDebugBuild = false
#endif

/// Thread-safe timing logger that writes to a file
/// Only logs in DEBUG builds or when ENABLE_TIMING_LOGGER environment variable is set
actor TimingLogger {
    static let shared = TimingLogger()
    
    private let logFileURL: URL
    private var isInitialized = false
    private let isEnabled: Bool
    
    private init() {
        // Enable logging in DEBUG builds or when explicitly enabled via environment variable
        let envEnabled = ProcessInfo.processInfo.environment["ENABLE_TIMING_LOGGER"]?.lowercased() == "true"
        isEnabled = isDebugBuild || envEnabled
        
        // Write to project root if we can find it (for workspace access), otherwise Documents directory
        // Try Xcode's SRCROOT environment variable first
        if let srcRoot = ProcessInfo.processInfo.environment["SRCROOT"] {
            logFileURL = URL(fileURLWithPath: srcRoot).appendingPathComponent("ios_agent_timing.log")
            if isEnabled {
                print("📝 iOS Timing Log: \(logFileURL.path)")
            }
        } else {
            // Fallback to Documents directory
            let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            logFileURL = documentsPath.appendingPathComponent("agent_timing.log")
            if isEnabled {
                print("📝 iOS Timing Log: \(logFileURL.path)")
            }
        }
    }
    
    private func ensureInitialized() {
        guard isEnabled else { return }
        if !isInitialized {
            let header = "=== Agent Timing Log - Started \(ISO8601DateFormatter().string(from: Date())) ===\n\n"
            if let data = header.data(using: .utf8) {
                try? data.write(to: logFileURL)
            }
            isInitialized = true
        }
    }
    
    func log(step: String, duration: TimeInterval? = nil, details: String? = nil) {
        guard isEnabled else { return }
        ensureInitialized()
        
        let timestamp = ISO8601DateFormatter().string(from: Date())
        var logLine = "[\(timestamp)] \(step)"
        
        if let duration = duration {
            logLine += ": \(String(format: "%.3f", duration))s"
        } else {
            logLine += ": START"
        }
        
        if let details = details {
            logLine += " | \(details)"
        }
        logLine += "\n"
        
        if let data = logLine.data(using: .utf8) {
            if let fileHandle = try? FileHandle(forWritingTo: logFileURL) {
                fileHandle.seekToEndOfFile()
                fileHandle.write(data)
                fileHandle.closeFile()
            } else {
                // If file doesn't exist, create it
                try? data.write(to: logFileURL)
            }
        }
    }
    
    func logStep(_ step: String, duration: TimeInterval, details: String? = nil) {
        log(step: step, duration: duration, details: details)
    }
    
    func logStart(_ step: String, details: String? = nil) {
        log(step: step, duration: nil, details: details)
    }
}
