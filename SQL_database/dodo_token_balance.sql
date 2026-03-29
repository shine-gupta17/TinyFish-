create table public.dodo_token_balance (
  id serial not null,
  provider_id text not null,
  total_tokens_purchased bigint not null default 0,
  tokens_consumed bigint not null default 0,
  tokens_remaining bigint not null default 0,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint dodo_token_balance_pkey primary key (id),
  constraint dodo_token_balance_provider_id_key unique (provider_id),
  constraint dodo_token_balance_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_dodo_token_balance_provider_id on public.dodo_token_balance using btree (provider_id) TABLESPACE pg_default;