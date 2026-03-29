create table public.chat_rag (
  id uuid not null default extensions.uuid_generate_v4 (),
  provider_id text null,
  platform_user_id text null,
  embedded boolean null,
  text text null,
  type text null,
  vectorstore_platform text null,
  input jsonb null,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint chat_rag_pkey primary key (id),
  constraint chat_rag_platform_user_id_key unique (platform_user_id),
  constraint chat_rag_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE
) TABLESPACE pg_default;    