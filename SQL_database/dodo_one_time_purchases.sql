create table public.dodo_one_time_purchases (
  id serial not null,
  dodo_payment_id text not null,
  dodo_customer_id text not null,
  provider_id text not null,
  package_key text not null,
  product_id text not null,
  quantity integer not null default 1,
  tokens_per_package bigint not null,
  total_tokens_purchased bigint GENERATED ALWAYS as ((tokens_per_package * quantity)) STORED null,
  tokens_consumed bigint not null default 0,
  tokens_remaining bigint GENERATED ALWAYS as (
    ((tokens_per_package * quantity) - tokens_consumed)
  ) STORED null,
  amount numeric(12, 2) not null,
  currency text not null default 'INR'::text,
  status text not null default 'pending'::text,
  metadata jsonb null default '{}'::jsonb,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint dodo_one_time_purchases_pkey primary key (id),
  constraint dodo_one_time_purchases_dodo_payment_id_key unique (dodo_payment_id),
  constraint dodo_one_time_purchases_provider_id_fkey foreign KEY (provider_id) references user_profiles (provider_id) on delete CASCADE,
  constraint dodo_one_time_purchases_quantity_check check ((quantity > 0)),
  constraint dodo_one_time_purchases_status_check check (
    (
      status = any (
        array[
          'pending'::text,
          'succeeded'::text,
          'failed'::text,
          'refunded'::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create index IF not exists idx_dodo_one_time_purchases_provider_id on public.dodo_one_time_purchases using btree (provider_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_one_time_purchases_payment_id on public.dodo_one_time_purchases using btree (dodo_payment_id) TABLESPACE pg_default;

create index IF not exists idx_dodo_one_time_purchases_status on public.dodo_one_time_purchases using btree (status) TABLESPACE pg_default;

create trigger update_dodo_one_time_purchases_updated_at BEFORE
update on dodo_one_time_purchases for EACH row
execute FUNCTION update_updated_at_column ();

create trigger auto_refresh_balance_on_purchase_change
after INSERT
or DELETE
or
update on dodo_one_time_purchases for EACH row
execute FUNCTION trigger_refresh_token_balance ();