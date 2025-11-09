-- Async agent jobs table for background processing of calendar events
create table if not exists public.async_agent_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users (id) on delete cascade,
    
    -- Job details
    job_type text not null,  -- 'calendar_sync', 'event_reminder', 'pattern_analysis', 'bulk_operation'
    job_status text not null default 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    priority integer not null default 5,  -- 1 (highest) to 10 (lowest)
    
    -- Job payload
    payload jsonb not null default '{}'::jsonb,  -- Job-specific parameters
    result jsonb,  -- Job result/output
    error_message text,  -- Error details if failed
    
    -- Agent context
    agent_action text,  -- Agent action to perform
    agent_state jsonb,  -- Full agent state for the job
    
    -- Scheduling
    scheduled_at timestamptz,  -- When to run (null = immediate)
    started_at timestamptz,  -- When job started processing
    completed_at timestamptz,  -- When job completed
    retry_count integer not null default 0,
    max_retries integer not null default 3,
    
    -- Metadata
    created_at timestamptz not null default timezone('utc'::text, now()),
    updated_at timestamptz not null default timezone('utc'::text, now()),
    
    -- Constraints
    constraint valid_job_status check (job_status in ('pending', 'running', 'completed', 'failed', 'cancelled')),
    constraint valid_priority check (priority >= 1 and priority <= 10),
    constraint valid_retry_count check (retry_count >= 0)
);

-- Indexes for job queue processing
create index if not exists idx_async_jobs_status_scheduled 
    on public.async_agent_jobs(job_status, scheduled_at nulls first, priority asc, created_at asc)
    where job_status in ('pending', 'running');

create index if not exists idx_async_jobs_user_id on public.async_agent_jobs(user_id);
create index if not exists idx_async_jobs_job_type on public.async_agent_jobs(job_type);
create index if not exists idx_async_jobs_created_at on public.async_agent_jobs(created_at desc);

-- GIN index for JSONB queries
create index if not exists idx_async_jobs_payload_gin 
    on public.async_agent_jobs using gin(payload);
create index if not exists idx_async_jobs_agent_state_gin 
    on public.async_agent_jobs using gin(agent_state);

-- Trigger to update updated_at
create trigger handle_async_jobs_updated_at
    before update on public.async_agent_jobs
    for each row
    execute procedure public.set_updated_at();

-- Row Level Security
alter table public.async_agent_jobs enable row level security;

-- Users can view their own jobs
create policy "Users can view their own async jobs"
    on public.async_agent_jobs
    for select
    using (auth.uid() = user_id);

-- Service role can manage all jobs
create policy "Service role can manage async jobs"
    on public.async_agent_jobs
    for all
    using (true)
    with check (true);

-- Comments
comment on table public.async_agent_jobs is 'Background jobs for async agent processing (calendar sync, reminders, bulk operations)';
comment on column public.async_agent_jobs.job_type is 'Type of background job (calendar_sync, event_reminder, pattern_analysis, bulk_operation)';
comment on column public.async_agent_jobs.agent_state is 'Full LangGraph agent state for the job execution';

