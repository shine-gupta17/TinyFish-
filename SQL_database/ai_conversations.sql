create table public.ai_conversations (
  ai_conversation_id uuid not null default extensions.uuid_generate_v4 (),
  automation_id uuid not null,
  platform_user_id text not null,
  model_provider public.model_provider_enum null default 'OPENAI'::model_provider_enum,
  model_name text not null default 'gpt-4o'::text,
  system_prompt text null default 'You are a helpful assistant.'::text,
  temperature numeric(2, 1) null default 0.7,
  is_rag_enabled boolean null default false,
  confidence_threshold numeric(3, 2) null default 0.75,
  updated_at timestamp with time zone null default now(),
  constraint ai_conversations_pkey primary key (ai_conversation_id),
  constraint ai_conversations_automation_id_key unique (automation_id),
  constraint ai_conversations_platform_user_id_key unique (platform_user_id),
  constraint ai_conversations_automation_id_fkey foreign KEY (automation_id) references automations (automation_id) on delete CASCADE
) TABLESPACE pg_default;