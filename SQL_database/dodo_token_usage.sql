create table public.dodo_token_usage (
  id serial not null,
  provider_id text not null,
  subscription_id text null,
  tokens_consumed bigint not null default 0,
  operation_type text null,
  dodo_event_id text null,
  reported_to_dodo boolean null default false,
  metadata jsonb null default '{}'::jsonb,
  consumed_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint dodo_token_usage_pkey primary key (id),
  constraint dodo_token_usage_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE,
  constraint dodo_token_usage_subscription_id_fkey foreign KEY (subscription_id) references dodo_subscriptions (dodo_subscription_id) on delete set null,
  constraint dodo_token_usage_tokens_consumed_check check ((tokens_consumed >= 0))
) TABLESPACE pg_default;

create index IF not exists idx_dodo_token_usage_provider_id on public.dodo_token_usage using btree (provider_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_token_usage_subscription_id on public.dodo_token_usage using btree (subscription_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_token_usage_consumed_at on public.dodo_token_usage using btree (consumed_at desc) TABLESPACE pg_default;

create index IF not exists idx_dodo_token_usage_reported on public.dodo_token_usage using btree (reported_to_dodo) TABLESPACE pg_default
where
  (reported_to_dodo = false);