create table public.plans (
  id serial not null,
  name text not null,
  monthly_price numeric(10, 2) not null,
  yearly_price numeric(10, 2) null,
  monthly_credits integer not null default 0,
  yearly_credits integer not null default 0,
  currency character(3) null default 'USD'::bpchar,
  metadata jsonb null default '{}'::jsonb,
  created_at timestamp without time zone null default now(),
  updated_at timestamp without time zone null default now(),
  constraint plans_pkey primary key (id),
  constraint plans_monthly_credits_check check ((monthly_credits >= 0)),
  constraint plans_yearly_credits_check check ((yearly_credits >= 0))
) TABLESPACE pg_default;