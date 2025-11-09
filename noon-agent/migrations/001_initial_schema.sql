-- Initial schema for Noon Calendar Agent
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',

    -- Google OAuth tokens
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_token_expiry TIMESTAMP WITH TIME ZONE,

    -- Primary calendar reference
    primary_calendar_id TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================================
-- CALENDARS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendars (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    google_calendar_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    is_primary BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique calendars per user
    UNIQUE(user_id, google_calendar_id)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_calendars_user_id ON calendars(user_id);
CREATE INDEX IF NOT EXISTS idx_calendars_google_id ON calendars(google_calendar_id);
CREATE INDEX IF NOT EXISTS idx_calendars_is_primary ON calendars(user_id, is_primary);

-- ============================================================================
-- FRIENDS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS friends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    google_calendar_id TEXT,
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique friends per user
    UNIQUE(user_id, email)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_friends_user_id ON friends(user_id);
CREATE INDEX IF NOT EXISTS idx_friends_email ON friends(email);
CREATE INDEX IF NOT EXISTS idx_friends_name ON friends(user_id, name);

-- ============================================================================
-- CALENDAR_EVENTS TABLE (cached from Google Calendar)
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    google_event_id TEXT NOT NULL,
    calendar_id UUID NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    location TEXT,
    attendees TEXT[] DEFAULT '{}',
    recurrence_rule TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique events per calendar
    UNIQUE(calendar_id, google_event_id)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_events_calendar_id ON calendar_events(calendar_id);
CREATE INDEX IF NOT EXISTS idx_events_google_id ON calendar_events(google_event_id);
CREATE INDEX IF NOT EXISTS idx_events_time_range ON calendar_events(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_events_summary ON calendar_events USING gin(to_tsvector('english', summary));

-- ============================================================================
-- USER_PREFERENCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Meeting preferences
    default_meeting_duration INTEGER DEFAULT 60,
    buffer_between_meetings INTEGER DEFAULT 0,
    allow_overlapping_events BOOLEAN DEFAULT FALSE,

    -- Work hours
    work_start_hour INTEGER DEFAULT 9,
    work_end_hour INTEGER DEFAULT 17,
    work_days INTEGER[] DEFAULT '{1,2,3,4,5}',  -- 1=Mon, 7=Sun

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster user preference lookups
CREATE INDEX IF NOT EXISTS idx_user_prefs_user_id ON user_preferences(user_id);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to all tables
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_calendars_updated_at
    BEFORE UPDATE ON calendars
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_friends_updated_at
    BEFORE UPDATE ON friends
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_calendar_events_updated_at
    BEFORE UPDATE ON calendar_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendars ENABLE ROW LEVEL SECURITY;
ALTER TABLE friends ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid()::TEXT = id::TEXT);

CREATE POLICY "Users can update own data" ON users
    FOR UPDATE USING (auth.uid()::TEXT = id::TEXT);

-- Calendars belong to users
CREATE POLICY "Users can view own calendars" ON calendars
    FOR SELECT USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can insert own calendars" ON calendars
    FOR INSERT WITH CHECK (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can update own calendars" ON calendars
    FOR UPDATE USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can delete own calendars" ON calendars
    FOR DELETE USING (auth.uid()::TEXT = user_id::TEXT);

-- Friends belong to users
CREATE POLICY "Users can view own friends" ON friends
    FOR SELECT USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can insert own friends" ON friends
    FOR INSERT WITH CHECK (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can update own friends" ON friends
    FOR UPDATE USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can delete own friends" ON friends
    FOR DELETE USING (auth.uid()::TEXT = user_id::TEXT);

-- Calendar events belong to user's calendars
CREATE POLICY "Users can view events from own calendars" ON calendar_events
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM calendars
            WHERE calendars.id = calendar_events.calendar_id
            AND calendars.user_id::TEXT = auth.uid()::TEXT
        )
    );

CREATE POLICY "Users can insert events to own calendars" ON calendar_events
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM calendars
            WHERE calendars.id = calendar_events.calendar_id
            AND calendars.user_id::TEXT = auth.uid()::TEXT
        )
    );

CREATE POLICY "Users can update events in own calendars" ON calendar_events
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM calendars
            WHERE calendars.id = calendar_events.calendar_id
            AND calendars.user_id::TEXT = auth.uid()::TEXT
        )
    );

CREATE POLICY "Users can delete events from own calendars" ON calendar_events
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM calendars
            WHERE calendars.id = calendar_events.calendar_id
            AND calendars.user_id::TEXT = auth.uid()::TEXT
        )
    );

-- User preferences belong to users
CREATE POLICY "Users can view own preferences" ON user_preferences
    FOR SELECT USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can insert own preferences" ON user_preferences
    FOR INSERT WITH CHECK (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can update own preferences" ON user_preferences
    FOR UPDATE USING (auth.uid()::TEXT = user_id::TEXT);

CREATE POLICY "Users can delete own preferences" ON user_preferences
    FOR DELETE USING (auth.uid()::TEXT = user_id::TEXT);
