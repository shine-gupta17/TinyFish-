create table public.transactions (
  id text not null,
  order_id text not null,
  provider_id text not null,
  amount numeric(12, 2) not null,
  currency character varying(10) not null,
  email character varying(255) null,
  contact character varying(50) null,
  status character varying(50) not null,
  billing_cycle character varying(20) null,
  platform text null,
  created_at timestamp without time zone null default now(),
  constraint transactions_pkey primary key (id),
  constraint transactions_billing_cycle_check check (
    (
      (billing_cycle)::text = any (
        (
          array[
            'monthly'::character varying,
            'yearly'::character varying
          ]
        )::text[]
      )
    )
  )
) TABLESPACE pg_default;