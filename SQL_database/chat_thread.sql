create table public.chat_thread (
  id serial not null,
  provider_id text not null,
  thread_id text not null,
  name text not null,
  config jsonb null,
  constraint chat_thread_pkey primary key (id)
) TABLESPACE pg_default;