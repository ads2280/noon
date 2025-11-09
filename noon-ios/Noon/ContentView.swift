//
//  ContentView.swift
//  Noon
//
//  Created by Jude Partovi on 11/8/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = AuthViewModel()
    @FocusState private var focusedField: Field?

    enum Field {
        case phone, code
    }

    var body: some View {
        NavigationStack {
            ZStack {
                backgroundGradient
                    .ignoresSafeArea()

                Group {
                    switch viewModel.phase {
                    case .enterPhone:
                        phoneEntry
                    case .enterCode:
                        codeEntry
                    case .authenticated:
                        AgentView()
                    }
                }
                .animation(.easeInOut, value: viewModel.phase)
            }
            .navigationTitle("Noon")
            .toolbar {
                if viewModel.phase == .authenticated {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Sign Out") {
                            viewModel.signOut()
                        }
                    }
                }
            }
            .toolbar(viewModel.phase == .authenticated ? .visible : .hidden, for: .navigationBar)
            .alert("Something went wrong", isPresented: Binding(
                get: { viewModel.errorMessage != nil },
                set: { value in
                    if !value {
                        viewModel.clearError()
                    }
                }
            )) {
                Button("OK", role: .cancel) {
                    viewModel.clearError()
                }
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }

    private var phoneEntry: some View {
        VStack(spacing: 32) {
            Spacer()

            Text("Welcome to Noon")
                .font(.system(size: 42, weight: .bold, design: .rounded))
                .foregroundStyle(ColorPalette.Text.primary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(alignment: .leading, spacing: 12) {
                Text("Phone Number")
                    .font(.headline)
                    .foregroundStyle(ColorPalette.Text.secondary)

                TextField("+1 555 123 4567", text: $viewModel.phoneNumber)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    .focused($focusedField, equals: .phone)
            }
            .padding(.horizontal, 32)

            Button {
                Task {
                    await viewModel.requestOTP()
                    if viewModel.phase == .enterCode {
                        focusedField = .code
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

    private var codeEntry: some View {
        VStack(spacing: 32) {
            Spacer()

            Text("Enter Verification Code")
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .foregroundStyle(ColorPalette.Text.primary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(alignment: .leading, spacing: 12) {
                Text("Code")
                    .font(.headline)
                    .foregroundStyle(ColorPalette.Text.secondary)

                TextField("123456", text: $viewModel.otpCode)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    .focused($focusedField, equals: .code)
            }
            .padding(.horizontal, 32)

            Button {
                Task {
                    await viewModel.verifyOTP()
                }
            } label: {
                if viewModel.isLoading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(ColorPalette.Text.inverted)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                } else {
                    Text("Verify & Continue")
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

            Button("Use a different number") {
                viewModel.signOut()
                focusedField = .phone
            }
            .foregroundStyle(ColorPalette.Text.secondary)

            Spacer()
        }
        .frame(maxWidth: 420)
        .padding()
    }

    private var backgroundGradient: some View {
        ZStack {
            ColorPalette.Gradients.backgroundBase

            ColorPalette.Gradients.backgroundAccentWarm
                .blendMode(.screen)
                .blur(radius: 20)
                .offset(x: -30, y: -50)

            ColorPalette.Gradients.backgroundAccentCool
                .blendMode(.screen)
                .blur(radius: 40)
                .offset(x: 60, y: 90)
        }
    }
}
