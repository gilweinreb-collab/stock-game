-- הריצו ב-Supabase: SQL Editor -> New query -> Run
create table if not exists public.game_state (
  id         int primary key,
  data       jsonb       not null,
  rev        int         not null default 1,   -- מספר גרסה: מונע דריסה כששני שחקנים סוחרים בו-זמנית
  updated_at timestamptz not null default now()
);

-- RLS מופעל וללא policies: אי אפשר לגשת לטבלה עם המפתח הציבורי (anon).
-- האפליקציה ניגשת עם המפתח הסודי (service_role / secret key) שנשמר רק ב-secrets.
alter table public.game_state enable row level security;
