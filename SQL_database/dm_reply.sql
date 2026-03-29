create table public.dm_reply (
  dm_reply_id uuid not null default extensions.uuid_generate_v4 (),
  automation_id uuid not null,
  platform_user_id text not null,
  provider_id text not null,
  trigger_type text not null,
  keywords text null,
  match_type text not null,
  ai_context_rules text null,
  reply_template_type text not null,
  reply_template_content text not null,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  constraint dm_reply_pkey primary key (dm_reply_id),
  constraint dm_reply_automation_id_fkey foreign KEY (automation_id) references automations (automation_id) on delete CASCADE
) TABLESPACE pg_default;