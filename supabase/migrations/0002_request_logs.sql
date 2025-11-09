-- Request logs table for tracking user interactions and building patterns/rulesets
create table if not exists public.request_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users (id) on delete cascade,
    
    -- Request details
    endpoint text not null,  -- e.g., '/agent/chat', '/agent/event'
    method text not null default 'POST',  -- HTTP method
    request_body jsonb,  -- Full request payload (sanitized if needed)
    request_headers jsonb,  -- Relevant headers (user-agent, etc.)
    
    -- Response details
    response_status integer,  -- HTTP status code
    response_body jsonb,  -- Response payload (can be large, consider indexing)
    response_time_ms integer,  -- Response time in milliseconds
    
    -- Agent-specific fields (for /agent/* endpoints)
    agent_action text,  -- 'create', 'read', 'update', 'delete', 'search', 'schedule'
    agent_tool text,  -- Tool name that was called
    agent_success boolean,  -- Whether agent operation succeeded
    agent_summary text,  -- Human-readable summary from agent
    
    -- Pattern analysis fields
    intent_category text,  -- Extracted intent category (e.g., 'schedule_meeting', 'view_calendar')
    entities jsonb,  -- Extracted entities (people, times, locations, etc.)
    user_pattern text,  -- Identified user pattern/rule
    
    -- Metadata
    ip_address inet,  -- Client IP (for rate limiting, geo analysis)
    user_agent text,  -- User agent string
    created_at timestamptz not null default timezone('utc'::text, now()),
    
    -- Indexes for common queries
    constraint valid_status_code check (response_status >= 100 and response_status < 600)
);

-- Indexes for fast queries
create index if not exists idx_request_logs_user_id on public.request_logs(user_id);
create index if not exists idx_request_logs_created_at on public.request_logs(created_at desc);
create index if not exists idx_request_logs_endpoint on public.request_logs(endpoint);
create index if not exists idx_request_logs_agent_action on public.request_logs(agent_action) where agent_action is not null;
create index if not exists idx_request_logs_user_pattern on public.request_logs(user_pattern) where user_pattern is not null;
create index if not exists idx_request_logs_intent_category on public.request_logs(intent_category) where intent_category is not null;

-- Composite index for user behavior analysis
create index if not exists idx_request_logs_user_behavior 
    on public.request_logs(user_id, created_at desc, agent_action, agent_success);

-- GIN index for JSONB queries on request_body and entities
create index if not exists idx_request_logs_request_body_gin 
    on public.request_logs using gin(request_body);
create index if not exists idx_request_logs_entities_gin 
    on public.request_logs using gin(entities);

-- Row Level Security
alter table public.request_logs enable row level security;

-- Users can only view their own request logs
create policy "Users can view their own request logs"
    on public.request_logs
    for select
    using (auth.uid() = user_id);

-- Service role can insert logs (for backend logging)
create policy "Service role can insert request logs"
    on public.request_logs
    for insert
    with check (true);  -- Backend will use service role key

-- Service role can update logs (for async processing)
create policy "Service role can update request logs"
    on public.request_logs
    for update
    using (true)
    with check (true);

-- Comments for documentation
comment on table public.request_logs is 'Logs all user requests to build patterns, rulesets, and analyze common use cases';
comment on column public.request_logs.agent_action is 'The action taken by the agent (create, read, update, delete, search, schedule)';
comment on column public.request_logs.intent_category is 'Categorized intent extracted from the request (e.g., schedule_meeting, view_calendar)';
comment on column public.request_logs.entities is 'Extracted entities from the request (people, times, locations, etc.)';
comment on column public.request_logs.user_pattern is 'Identified user pattern or rule that matches this request';

