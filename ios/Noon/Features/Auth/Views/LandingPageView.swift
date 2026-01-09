//
//  LandingPageView.swift
//  Noon
//
//  Created by GPT-5 Codex on 11/12/25.
//

import SwiftUI

struct LandingPageView: View {
    @EnvironmentObject private var viewModel: AuthViewModel
    let focusedField: FocusState<ContentView.Field?>.Binding

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            Text("noon")
                .font(.system(size: 52, weight: .bold, design: .rounded))
                .foregroundStyle(ColorPalette.Gradients.primary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(alignment: .leading, spacing: 12) {
                Text("Phone Number")
                    .font(.headline)
                    .foregroundStyle(ColorPalette.Text.secondary)

                TextField(
                    "555 123 4567",
                    text: $viewModel.phoneNumber
                )
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    .focused(focusedField, equals: .phone)
            }
            .padding(.horizontal, 32)

            Button {
                Task {
                    await viewModel.requestOTP()
                    if viewModel.phase == .enterCode {
                        focusedField.wrappedValue = .code
                    }
                }
            } label: {
                if viewModel.isLoading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(ColorPalette.Text.inverted)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                } else {
                    Text("Send Code")
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(ColorPalette.Text.inverted)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                }
            }
            .buttonStyle(.plain)
            .background(ColorPalette.Gradients.primary)
            .clipShape(Capsule())
            .shadow(
                color: ColorPalette.Semantic.primary.opacity(0.35),
                radius: 24,
                x: 0,
                y: 14
            )
            .padding(.horizontal, 40)
            .disabled(viewModel.isLoading)

            Spacer()
        }
        .frame(maxWidth: 420)
        .padding()
    }
}



