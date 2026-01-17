-- Link calendars to Google accounts
-- This allows the same calendar to exist multiple times (once per Google account connection)
-- and ensures each calendar entry knows which Google account it came from

-- Add google_account_id column to calendars table
alter table public.calendars
    add column if not exists google_account_id uuid;

-- Drop the old unique constraint
alter table public.calendars
    drop constraint if exists calendars_user_id_google_calendar_id_key;

-- Add foreign key constraint to google_accounts
alter table public.calendars
    add constraint calendars_google_account_id_fkey 
    foreign key (google_account_id) 
    references public.google_accounts (id) 
    on delete cascade;

-- Add new unique constraint on (google_account_id, google_calendar_id)
alter table public.calendars
    add constraint calendars_google_account_id_google_calendar_id_key 
    unique (google_account_id, google_calendar_id);

-- Add index on google_account_id for performance
create index if not exists idx_calendars_google_account_id 
    on public.calendars using btree (google_account_id);

-- Make google_account_id required (NOT NULL)
-- Note: This will fail if there are existing rows, but user will delete and re-add accounts
alter table public.calendars
    alter column google_account_id set not null;
