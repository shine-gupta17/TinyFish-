create table public.dodo_webhook_events (
  id serial not null,
  event_id text null,
  event_type text not null,
  processed boolean null default false,
  processing_error text null,
  payload jsonb not null,
  received_at timestamp with time zone null default timezone ('utc'::text, now()),
  processed_at timestamp with time zone null,
  constraint dodo_webhook_events_pkey primary key (id),
  constraint dodo_webhook_events_event_id_key unique (event_id)
) TABLESPACE pg_default;

create index IF not exists idx_dodo_webhook_events_event_type on public.dodo_webhook_events using btree (event_type) TABLESPACE pg_default;

create index IF not exists idx_dodo_webhook_events_processed on public.dodo_webhook_events using btree (processed) TABLESPACE pg_default
where
  (processed = false);

create index IF not exists idx_dodo_webhook_events_received_at on public.dodo_webhook_events using btree (received_at desc) TABLESPACE pg_default;