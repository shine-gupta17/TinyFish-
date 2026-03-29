create table public.chat_agent (
  id bigserial not null,
  stream_type text null,
  provider_id text null,
  thread_id text null,
  query_id text null,
  role text null,
  node text null,
  next_node text null,
  node_type text null,
  next_node_type text null,
  type text null,
  next_type text null,
  message text null,
  reason text null,
  current_messages jsonb null,
  params jsonb null,
  embedding public.vector null,
  tool_output jsonb null,
  usage jsonb null,
  status text null,
  total_token bigint null,
  total_cost double precision null,
  data jsonb null,
  execution_time timestamp with time zone null default now(),
  constraint chat_agent_pkey primary key (id),
  constraint chat_agent_status_check check (
    (
      status = any (
        array['success'::text, 'failed'::text, 'started'::text]
      )
    )
  )
) TABLESPACE pg_default;