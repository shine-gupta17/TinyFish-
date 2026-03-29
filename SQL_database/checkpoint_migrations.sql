create table public.checkpoint_migrations (
  v integer not null,
  constraint checkpoint_migrations_pkey primary key (v)
) TABLESPACE pg_default;