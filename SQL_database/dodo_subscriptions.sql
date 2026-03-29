create table public.dodo_subscriptions (
  id serial not null,
  dodo_subscription_id text not null,
  dodo_customer_id text not null,
  dodo_payment_id text null,
  provider_id text not null,
  plan_type text not null,
  product_id text not null,
  status text not null default 'pending'::text,
  tokens_allocated bigint not null default 0,
  tokens_consumed bigint not null default 0,
  tokens_remaining bigint GENERATED ALWAYS as ((tokens_allocated - tokens_consumed)) STORED null,
  billing_interval text null,
  currency text not null default 'INR'::text,
  amount numeric(12, 2) not null,
  current_period_start timestamp with time zone null,
  current_period_end timestamp with time zone null,
  next_billing_date timestamp with time zone null,
  cancelled_at timestamp with time zone null,
  metadata jsonb null default '{}'::jsonb,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint dodo_subscriptions_pkey primary key (id),
  constraint dodo_subscriptions_dodo_subscription_id_key unique (dodo_subscription_id),
  constraint dodo_subscriptions_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE,
  constraint dodo_subscriptions_status_check check (
    (
      status = any (
        array[
          'pending'::text,
          'active'::text,
          'on_hold'::text,
          'cancelled'::text,
          'failed'::text,
          'expired'::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create index IF not exists idx_dodo_subscriptions_dodo_customer_id on public.dodo_subscriptions using btree (dodo_customer_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_subscriptions_next_billing_date on public.dodo_subscriptions using btree (next_billing_date) TABLESPACE pg_default
where
  (status = 'active'::text);

create index IF not exists idx_dodo_subscriptions_provider_id on public.dodo_subscriptions using btree (provider_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_subscriptions_status on public.dodo_subscriptions using btree (status) TABLESPACE pg_default;

create index IF not exists idx_dodo_subscriptions_dodo_subscription_id on public.dodo_subscriptions using btree (dodo_subscription_id) TABLESPACE pg_default;

create trigger update_dodo_subscriptions_updated_at BEFORE
update on dodo_subscriptions for EACH row
execute FUNCTION update_updated_at_column ();

create trigger auto_refresh_balance_on_subscription_change
after INSERT
or DELETE
or
update on dodo_subscriptions for EACH row
execute FUNCTION trigger_refresh_token_balance ();