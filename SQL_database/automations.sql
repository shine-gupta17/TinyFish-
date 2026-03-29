create table public.automations (
  automation_id uuid not null default extensions.uuid_generate_v4 (),
  platform public.platform_enum not null,
  platform_user_id text not null,
  name character varying(255) not null,
  description text null,
  automation_type text not null,
  activation_status text null default 'ACTIVE'::text,
  health_status public.automation_health_status null default 'HEALTHY'::automation_health_status,
  model_usage text null default 'PLATFORM_DEFAULT'::text,
  cumulative_cost numeric(10, 6) null default 0.00,
  execution_count integer null default 0,
  last_triggered_at timestamp with time zone null,
  start_date timestamp with time zone null,
  end_date timestamp with time zone null,
  max_actions integer null,
  time_period_seconds integer null,
  user_cooldown_seconds integer null,
  schedule_type text not null,
  scheduled_at timestamp with time zone null,
  recurring_schedule text null,
  auto_deactivate boolean null default false,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  cumulative_tokens integer null default 0,
  constraint automations_pkey primary key (automation_id),
  constraint automations_activation_status_check check (
    (
      activation_status = any (
        array['ACTIVE'::text, 'PAUSED'::text, 'SCHEDULED'::text]
      )
    )
  ),
  constraint automations_automation_type_check check (
    (
      automation_type = any (
        array[
          'AI_DM_CONVERSATION'::text,
          'DM_REPLY'::text,
          'COMMENT_REPLY'::text,
          'PRIVATE_MESSAGE'::text
        ]
      )
    )
  ),
  constraint automations_check check (
    (
      (
        (schedule_type = 'ONE_TIME'::text)
        and (scheduled_at is not null)
        and (recurring_schedule is null)
      )
      or (
        (schedule_type = 'RECURRING'::text)
        and (scheduled_at is null)
        and (recurring_schedule is not null)
      )
      or (
        (schedule_type = 'CONTINUOUS'::text)
        and (scheduled_at is null)
        and (recurring_schedule is null)
      )
    )
  ),
  constraint automations_model_usage_check check (
    (
      model_usage = any (
        array['PLATFORM_DEFAULT'::text, 'USER_CUSTOM'::text]
      )
    )
  ),
  constraint automations_schedule_type_check check (
    (
      schedule_type = any (
        array[
          'ONE_TIME'::text,
          'RECURRING'::text,
          'CONTINUOUS'::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create unique INDEX IF not exists unique_ai_dm_conversation_per_user on public.automations using btree (platform_user_id) TABLESPACE pg_default
where
  (automation_type = 'AI_DM_CONVERSATION'::text);