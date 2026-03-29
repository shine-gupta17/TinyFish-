create table public.checkpoint_blobs (
  thread_id text not null,
  checkpoint_ns text not null default ''::text,
  channel text not null,
  version text not null,
  type text not null,
  blob bytea null,
  constraint checkpoint_blobs_pkey primary key (thread_id, checkpoint_ns, channel, version)
) TABLESPACE pg_default;

create index IF not exists checkpoint_blobs_thread_id_idx on public.checkpoint_blobs using btree (thread_id) TABLESPACE pg_default;