create table public.checkpoints (
  thread_id text not null,
  checkpoint_ns text not null default ''::text,
  checkpoint_id text not null,
  parent_checkpoint_id text null,
  type text null,
  checkpoint jsonb not null,
  metadata jsonb not null default '{}'::jsonb,
  constraint checkpoints_pkey primary key (thread_id, checkpoint_ns, checkpoint_id)
) TABLESPACE pg_default;

create index IF not exists checkpoints_thread_id_idx on public.checkpoints using btree (thread_id) TABLESPACE pg_default;