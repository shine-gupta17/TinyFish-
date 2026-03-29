create table public.rag_data_sources (
  source_id uuid not null default extensions.uuid_generate_v4 (),
  automation_id uuid not null,
  platform public.platform_enum not null,
  platform_user_id text not null,
  rag_source_type public.rag_source_type not null,
  input_source text not null,
  content text null,
  processing_status public.processing_status null default 'PENDING'::processing_status,
  vector_db_provider text null default 'pinecone'::text,
  error_message text null,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  file_url text null,
  website_url text null,
  constraint rag_data_sources_pkey primary key (source_id),
  constraint unique_platform_user_source unique (platform, platform_user_id),
  constraint rag_data_sources_automation_id_fkey foreign KEY (automation_id) references automations (automation_id) on delete CASCADE
) TABLESPACE pg_default;