-- Restore the full Noon calendar agent schema so the LangGraph worker
-- can hydrate user context (calendars, friends, preferences, cached events).

create extension if not exists "uuid-ossp";

-- Extend the existing users table with the columns expected by noon-agent.
alter table public.users
    add column if not exists email text,
    add column if not exists full_name text,
    add column if not exists timezone text not null default 'UTC',
    add column if not exists google_access_token text,
    add column if not exists google_refresh_token text,
    add column if not exists google_token_expiry timestamptz,
    add column if not exists primary_calendar_id text;

create index if not exists idx_users_email on public.users (email);

-- Calendars linked to each user (sync'd from Google)
create table if not exists public.calendars (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references public.users (id) on delete cascade,
    google_calendar_id text not null,
    name text not null,
    description text,
    color text,
    is_primary boolean default false,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now()),
    unique (user_id, google_calendar_id)
);

create index if not exists idx_calendars_user_id on public.calendars (user_id);
create index if not exists idx_calendars_google_id on public.calendars (google_calendar_id);
create index if not exists idx_calendars_is_primary on public.calendars (user_id, is_primary);

-- Friends/contacts with optional calendar IDs for fuzzy attendee matching
create table if not exists public.friends (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null references public.users (id) on delete cascade,
    name text not null,
    email text not null,
    google_calendar_id text,
    notes text,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now()),
    unique (user_id, email)
);

create index if not exists idx_friends_user_id on public.friends (user_id);
create index if not exists idx_friends_email on public.friends (email);
create index if not exists idx_friends_name on public.friends (user_id, name);

-- Optional cache of events pulled from Google Calendar
create table if not exists public.calendar_events (
    id uuid primary key default uuid_generate_v4(),
    google_event_id text not null,
    calendar_id uuid not null references public.calendars (id) on delete cascade,
    summary text not null,
    description text,
    start_time timestamptz not null,
    end_time timestamptz not null,
    location text,
    attendees text[] default '{}'::text[],
    recurrence_rule text,
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now()),
    unique (calendar_id, google_event_id)
);

create index if not exists idx_events_calendar_id on public.calendar_events (calendar_id);
create index if not exists idx_events_google_id on public.calendar_events (google_event_id);
create index if not exists idx_events_time_range on public.calendar_events (start_time, end_time);
create index if not exists idx_events_summary on public.calendar_events using gin (to_tsvector('english', summary));

-- User-level meeting preferences (1:1 with users)
create table if not exists public.user_preferences (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid not null unique references public.users (id) on delete cascade,
    default_meeting_duration integer default 60,
    buffer_between_meetings integer default 0,
    allow_overlapping_events boolean default false,
    work_start_hour integer default 9,
    work_end_hour integer default 17,
    work_days integer[] default '{1,2,3,4,5}',
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now())
);

create index if not exists idx_user_prefs_user_id on public.user_preferences (user_id);

-- Reuse the shared updated_at trigger for the new tables.
create trigger handle_calendars_updated_at
    before update on public.calendars
    for each row
    execute procedure public.set_updated_at();

create trigger handle_friends_updated_at
    before update on public.friends
    for each row
    execute procedure public.set_updated_at();

create trigger handle_calendar_events_updated_at
    before update on public.calendar_events
    for each row
    execute procedure public.set_updated_at();

create trigger handle_user_preferences_updated_at
    before update on public.user_preferences
    for each row
    execute procedure public.set_updated_at();

-- Enable RLS and ensure users only see their own data.
alter table public.calendars enable row level security;
alter table public.friends enable row level security;
alter table public.calendar_events enable row level security;
alter table public.user_preferences enable row level security;

create policy "Users can view own calendars"
    on public.calendars for select
    using (auth.uid() = user_id);

create policy "Users can insert own calendars"
    on public.calendars for insert
    with check (auth.uid() = user_id);

create policy "Users can update own calendars"
    on public.calendars for update
    using (auth.uid() = user_id);

create policy "Users can delete own calendars"
    on public.calendars for delete
    using (auth.uid() = user_id);

create policy "Users can view own friends"
    on public.friends for select
    using (auth.uid() = user_id);

create policy "Users can insert own friends"
    on public.friends for insert
    with check (auth.uid() = user_id);

create policy "Users can update own friends"
    on public.friends for update
    using (auth.uid() = user_id);

create policy "Users can delete own friends"
    on public.friends for delete
    using (auth.uid() = user_id);

create policy "Users can view own events"
    on public.calendar_events for select
    using (
        exists (
            select 1
            from public.calendars c
            where c.id = calendar_events.calendar_id
              and c.user_id = auth.uid()
        )
    );

create policy "Users can insert own events"
    on public.calendar_events for insert
    with check (
        exists (
            select 1
            from public.calendars c
            where c.id = calendar_events.calendar_id
              and c.user_id = auth.uid()
        )
    );

create policy "Users can update own events"
    on public.calendar_events for update
    using (
        exists (
            select 1
            from public.calendars c
            where c.id = calendar_events.calendar_id
              and c.user_id = auth.uid()
        )
    );

create policy "Users can delete own events"
    on public.calendar_events for delete
    using (
        exists (
            select 1
            from public.calendars c
            where c.id = calendar_events.calendar_id
              and c.user_id = auth.uid()
        )
    );

create policy "Users can view own preferences"
    on public.user_preferences for select
    using (auth.uid() = user_id);

create policy "Users can insert own preferences"
    on public.user_preferences for insert
    with check (auth.uid() = user_id);

create policy "Users can update own preferences"
    on public.user_preferences for update
    using (auth.uid() = user_id);

create policy "Users can delete own preferences"
    on public.user_preferences for delete
    using (auth.uid() = user_id);
