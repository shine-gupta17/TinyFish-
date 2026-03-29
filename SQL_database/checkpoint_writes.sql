create table public.checkpoint_writes (
  thread_id text not null,
  checkpoint_ns text not null default ''::text,
  checkpoint_id text not null,
  task_id text not null,
  idx integer not null,
  channel text not null,
  type text null,
  blob bytea not null,
  task_path text not null default ''::text,
  constraint checkpoint_writes_pkey primary key (
    thread_id,
    checkpoint_ns,
    checkpoint_id,
    task_id,
    idx
  )
) TABLESPACE pg_default;

create index IF not exists checkpoint_writes_thread_id_idx on public.checkpoint_writes using btree (thread_id) TABLESPACE pg_default;