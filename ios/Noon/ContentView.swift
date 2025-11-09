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
    @State private var navigationPath = NavigationPath()

    enum Field {
        case phone, code
    }

    private enum Destination: Hashable {
        case calendars
    }

    var body: some View {
        NavigationStack(path: $navigationPath) {
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
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("noon")
                        .font(.system(size: 20, weight: .semibold, design: .rounded))
                        .foregroundStyle(ColorPalette.Gradients.primary)
                }
                if viewModel.phase == .authenticated {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Menu {
                            Button("Calendar Accounts") {
                                navigationPath.append(Destination.calendars)
                            }
                            Button("Friends") {
                                // Coming soon
                            }
                            Divider()
                            Button(role: .destructive) {
                                viewModel.signOut()
                            } label: {
                                Text("Sign Out")
                            }
                        } label: {
                            Image(systemName: "line.3.horizontal")
                                .imageScale(.large)
                                .foregroundStyle(ColorPalette.Text.primary)
                        }
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
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
            .navigationDestination(for: Destination.self) { destination in
                switch destination {
                case .calendars:
                    if viewModel.session != nil {
                        CalendarsView(authViewModel: viewModel)
                    } else {
                        calendarsUnavailableFallback
                    }
                }
            }
        }
        .environmentObject(viewModel)
    }

    private var phoneEntry: some View {
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
                    text: Binding(
                        get: { viewModel.phoneNumber },
                        set: { newValue in
                            viewModel.phoneNumber = PhoneNumberFormatter.formatDisplay(from: newValue)
                        }
                    )
                )
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

    private var calendarsUnavailableFallback: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .imageScale(.large)
                .foregroundStyle(ColorPalette.Semantic.warning)
            Text("We couldn't load your calendars. Please sign in again.")
                .multilineTextAlignment(.center)
                .foregroundStyle(ColorPalette.Text.secondary)
            Button("Sign Out") {
                viewModel.signOut()
            }
            .foregroundStyle(ColorPalette.Text.primary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(ColorPalette.Surface.background.ignoresSafeArea())
    }
}

private enum PhoneNumberFormatter {
    static func formatDisplay(from input: String) -> String {
        let digitsOnly = input.filter(\.isNumber)

        guard digitsOnly.isEmpty == false else { return "" }

        var digits = digitsOnly

        if digits.count >= 11, digits.hasPrefix("1") {
            digits = String(digits.dropFirst())
        }

        if digits.count > 10 {
            digits = String(digits.prefix(10))
        }

        let area = String(digits.prefix(3))
        let middle = String(digits.dropFirst(min(3, digits.count)).prefix(3))
        let last = String(digits.dropFirst(min(6, digits.count)))

        var formatted = ""

        if area.isEmpty == false {
            formatted += "(\(area)"
            if area.count == 3 {
                formatted += ")"
                if digits.count > 3 {
                    formatted += " "
                }
            }
        }

        if middle.isEmpty == false {
            formatted += middle
            if middle.count == 3, last.isEmpty == false {
                formatted += " - "
            }
        }

        if last.isEmpty == false {
            formatted += last
        }

        return formatted
    }
}
