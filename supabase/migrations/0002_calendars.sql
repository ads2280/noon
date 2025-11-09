CREATE TABLE IF NOT EXISTS public.calendars (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    google_calendar_id text NOT NULL,
    name text NOT NULL,
    description text,
    color text,
    is_primary boolean DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE (user_id, google_calendar_id)
);

CREATE INDEX IF NOT EXISTS idx_calendars_user_id ON public.calendars (user_id);
CREATE INDEX IF NOT EXISTS idx_calendars_google_id ON public.calendars (google_calendar_id);
CREATE INDEX IF NOT EXISTS idx_calendars_is_primary ON public.calendars (user_id, is_primary);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := timezone('utc'::text, now());
    RETURN NEW;
END;
$$;

CREATE TRIGGER handle_calendars_updated_at
    BEFORE UPDATE ON public.calendars
    FOR EACH ROW
    EXECUTE PROCEDURE public.set_updated_at();

ALTER TABLE public.calendars ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own calendars"
    ON public.calendars
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own calendars"
    ON public.calendars
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
