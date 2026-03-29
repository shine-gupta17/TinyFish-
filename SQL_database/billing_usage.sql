create table public.billing_usage (
  id serial not null,
  provider_id text not null,
  chat_token bigint null default 0,
  chat_cost numeric(12, 4) null default 0.0,
  platform_automation_count integer null default 0,
  platform_automation_token bigint null default 0,
  current_credits numeric(12, 2) null default 0.0,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint billing_usage_pkey primary key (id),
  constraint billing_usage_provider_id_key unique (provider_id),
  constraint billing_usage_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE
) TABLESPACE pg_default;