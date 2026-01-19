-- Add is_hidden column to calendars table
-- Allows users to hide calendars from schedule views and agent access
-- Hidden calendars will not appear in any schedule queries, event listings, or be accessible to the agent

alter table public.calendars
    add column if not exists is_hidden boolean not null default false;

-- Add comment explaining the column
comment on column public.calendars.is_hidden is 'Whether this calendar is hidden from schedule views and agent access. Hidden calendars are only visible in the calendar accounts management page.';

-- Add index for efficient filtering by is_hidden
create index if not exists idx_calendars_is_hidden 
    on public.calendars using btree (is_hidden);

-- Add composite index for filtering by user_id and is_hidden (common query pattern)
create index if not exists idx_calendars_user_id_is_hidden 
    on public.calendars using btree (user_id, is_hidden);
