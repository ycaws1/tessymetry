-- Run once in Supabase SQL Editor if the table was created from an older schema.sql
-- that only allowed teslemetry/raw/splunk. New events use format = 'tesla' for dict payloads.

alter table public.telemetry_events
  drop constraint if exists telemetry_events_format_check;

alter table public.telemetry_events
  add constraint telemetry_events_format_check
  check (format in ('tesla', 'teslemetry', 'raw', 'splunk'));
