create table if not exists public.planner_sessions (
  id text primary key,
  profile jsonb not null default '{}'::jsonb,
  messages jsonb not null default '[]'::jsonb,
  summary text not null default '',
  summary_mode text not null default 'local',
  summary_error text not null default '',
  last_plan text not null default '',
  route_cities jsonb not null default '[]'::jsonb,
  route_line jsonb not null default '[]'::jsonb,
  route_source text not null default '',
  updated_at timestamptz not null default now()
);

alter table public.planner_sessions enable row level security;