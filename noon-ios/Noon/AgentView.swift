//
//  AgentView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/8/25.
//

import SwiftUI

struct AgentView: View {
    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            Text("Agent")
                .font(.largeTitle.weight(.bold))
                .foregroundStyle(ColorPalette.Text.primary)
            Text("This screen will host the agent experience.")
                .foregroundStyle(ColorPalette.Text.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(ColorPalette.Gradients.backgroundBase.ignoresSafeArea())
    }
}

#Preview {
    AgentView()
}

