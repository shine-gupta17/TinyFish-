create table public.connected_accounts (
  id serial not null,
  provider_id text not null,
  platform text not null,
  platform_user_id text not null,
  platform_username text not null,
  profile_picture text null,
  locale text null default 'en_US'::text,
  scopes text[] null,
  data jsonb null,
  access_token text null,
  refresh_token text null,
  token_expires_at timestamp with time zone null,
  connected boolean null default true,
  connected_at timestamp with time zone null default timezone ('utc'::text, now()),
  disconnected_at timestamp with time zone null,
  last_synced_at timestamp with time zone null,
  is_primary boolean null default false,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint connected_accounts_pkey primary key (id),
  constraint connected_accounts_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE
) TABLESPACE pg_default;

create unique INDEX IF not exists unique_platform_user on public.connected_accounts using btree (platform_user_id, platform) TABLESPACE pg_default;