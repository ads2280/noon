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
    @State private var showFriendsComingSoonAlert = false

    enum Field {
        case phone, code
    }

    private enum Destination: Hashable {
        case calendars
        case codeVerification
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
                        // This view is shown via navigation, but we keep this for state consistency
                        EmptyView()
                    case .authenticated:
                        AgentView()
                    }
                }
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
                                showFriendsComingSoonAlert = true
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
            .toolbar(viewModel.phase == .enterPhone ? .hidden : .visible, for: .navigationBar)
            .navigationDestination(for: Destination.self) { destination in
                switch destination {
                case .calendars:
                    if viewModel.session != nil {
                        CalendarAccountsView(authViewModel: viewModel)
                    } else {
                        calendarsUnavailableFallback
                    }
                case .codeVerification:
                    CodeVerificationView(focusedField: $focusedField)
                }
            }
            .onChange(of: viewModel.phase) { oldPhase, newPhase in
                if newPhase == .enterCode && oldPhase == .enterPhone {
                    navigationPath.append(Destination.codeVerification)
                } else if newPhase == .authenticated && oldPhase == .enterCode {
                    // Clear navigation path when authenticated so we show the agent view
                    if navigationPath.isEmpty == false {
                        navigationPath = NavigationPath()
                    }
                }
            }
            .onChange(of: navigationPath.count) { oldCount, newCount in
                // If navigation path is popped (count decreased) and we're on code phase, go back to phone
                if newCount < oldCount && viewModel.phase == .enterCode {
                    viewModel.signOut()
                    focusedField = .phone
                }
            }
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
            .alert("Coming Soon", isPresented: $showFriendsComingSoonAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text("This feature is not yet implemented.")
            }
        }
        .environmentObject(viewModel)
        .task {
            // Restore session from Supabase on app launch
            await viewModel.restoreSessionIfNeeded()
        }
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
