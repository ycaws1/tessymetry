-- Run this in the Supabase SQL Editor (Dashboard → SQL).
-- Uses service role from the app; enable RLS only if you also add policies for anon/authenticated.

create extension if not exists "pgcrypto";

create table if not exists public.telemetry_events (
  id uuid primary key default gen_random_uuid(),
  vin text not null,
  event_created_at timestamptz not null,
  received_at timestamptz not null default now(),
  format text not null check (format in ('teslemetry', 'raw', 'splunk')),
  payload jsonb not null,
  flattened jsonb not null default '{}'::jsonb
);

create index if not exists idx_telemetry_vin_event_time
  on public.telemetry_events (vin, event_created_at desc);

create index if not exists idx_telemetry_received
  on public.telemetry_events (received_at desc);

comment on table public.telemetry_events is 'Teslemetry webhook payloads (all formats) with flattened fields for querying.';
