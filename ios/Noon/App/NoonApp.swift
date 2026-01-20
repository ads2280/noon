//
//  NoonApp.swift
//  Noon
//
//  Created by Jude Partovi on 11/8/25.
//

import SwiftUI

@main
struct NoonApp: App {
    init() {
        // Configure log suppression at app startup
        // This reduces verbose system warnings in development/Simulator builds
        LogSuppression.configure()
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
