-- ============================================================================
-- AuditTrail AI — Supabase schema (v2)
--
-- Run once in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Creates the product tables, grants the API roles access, and enables
-- row-level security so one firm can never read another firm's audits.
--
-- The earlier `documents` / `audit_results` tables from the first prototype are
-- left untouched; this version uses `at_` prefixed tables so it can be applied
-- to an existing project without destructive changes.
-- ============================================================================

create extension if not exists pgcrypto;

-- ------------------------------------------------------------------ tables --
create table if not exists public.at_profiles (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  email       text,
  plan        text not null default 'free'
              check (plan in ('free', 'pro', 'firm', 'enterprise')),
  org_name    text,
  created_at  timestamptz not null default now()
);

create table if not exists public.at_audits (
  id          uuid primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now(),
  title       text not null default 'Untitled lease audit',
  status      text not null default 'success'
              check (status in ('success', 'blocked', 'failed')),
  risk_level  text check (risk_level in ('LOW', 'MEDIUM', 'HIGH')),
  score       integer check (score between 0 and 100),
  -- The full audit record. Contains only the pseudonymised document; raw
  -- identifiers and the re-identification key are never written here.
  record      jsonb not null
);

create table if not exists public.at_leads (
  id          bigserial primary key,
  email       text not null,
  company     text,
  note        text,
  created_at  timestamptz not null default now()
);

create index if not exists at_audits_user_idx on public.at_audits (user_id, created_at desc);
create index if not exists at_audits_status_idx on public.at_audits (status);

create table if not exists public.at_api_keys (
  key_hash    text primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  label       text,
  prefix      text,
  created_at  timestamptz not null default now(),
  last_used   timestamptz
);

create index if not exists at_api_keys_user_idx on public.at_api_keys (user_id);

-- ------------------------------------------------------------- privileges ---
-- Tables created through the SQL editor do not always inherit the grants the
-- PostgREST roles need. Grant explicitly, then let RLS do the filtering.
grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on public.at_profiles to authenticated, service_role;
grant select, insert, update, delete on public.at_audits   to authenticated, service_role;
grant usage, select on sequence public.at_leads_id_seq     to service_role;
grant select, insert, update, delete on public.at_leads    to service_role;
grant select, insert, update, delete on public.at_api_keys to authenticated, service_role;

alter table public.at_profiles enable row level security;
alter table public.at_audits   enable row level security;
alter table public.at_leads    enable row level security;
alter table public.at_api_keys enable row level security;

-- ------------------------------------------------------------------- RLS ----
drop policy if exists "profiles: read own"   on public.at_profiles;
drop policy if exists "profiles: insert own" on public.at_profiles;
drop policy if exists "profiles: update own" on public.at_profiles;

create policy "profiles: read own"
  on public.at_profiles for select to authenticated
  using (auth.uid() = user_id);

create policy "profiles: insert own"
  on public.at_profiles for insert to authenticated
  with check (auth.uid() = user_id);

create policy "profiles: update own"
  on public.at_profiles for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "audits: read own"   on public.at_audits;
drop policy if exists "audits: insert own" on public.at_audits;
drop policy if exists "audits: delete own" on public.at_audits;

create policy "audits: read own"
  on public.at_audits for select to authenticated
  using (auth.uid() = user_id);

create policy "audits: insert own"
  on public.at_audits for insert to authenticated
  with check (auth.uid() = user_id);

create policy "audits: delete own"
  on public.at_audits for delete to authenticated
  using (auth.uid() = user_id);

-- Leads are written by the backend with the service role only; no policy is
-- created for anon/authenticated, so RLS denies them by default.

drop policy if exists "api keys: read own" on public.at_api_keys;
create policy "api keys: read own"
  on public.at_api_keys for select to authenticated
  using (auth.uid() = user_id);

-- --------------------------------------------------------------- triggers ---
create or replace function public.at_handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.at_profiles (user_id, email, plan)
  values (new.id, new.email, 'free')
  on conflict (user_id) do update set email = excluded.email;
  return new;
end;
$$;

drop trigger if exists at_on_auth_user_created on auth.users;
create trigger at_on_auth_user_created
  after insert on auth.users
  for each row execute function public.at_handle_new_user();

-- ------------------------------------------------------------- verification -
-- After running, this should list the policies above and return no rows for
-- the audit table when queried as an anonymous user.
--
--   select tablename, policyname, cmd from pg_policies
--   where schemaname = 'public' and tablename like 'at\_%' order by 1,2;
--
-- Then set SUPABASE_SCHEMA_READY=true in .env (optional; the server probes the
-- schema automatically and reports the active backend at /api/v1/health).
