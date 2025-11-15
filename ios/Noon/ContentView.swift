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
                        LandingPageView(focusedField: $focusedField)
                    case .enterCode:
                        CodeVerificationView(focusedField: $focusedField)
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
                        CalendarAccountsView(authViewModel: viewModel)
                    } else {
                        calendarsUnavailableFallback
                    }
                }
            }
        }
        .environmentObject(viewModel)
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
