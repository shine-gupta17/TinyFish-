create table public.waitlist (
  id serial not null,
  email character varying(255) not null,
  joined_at timestamp without time zone null default now(),
  constraint waitlist_pkey primary key (id),
  constraint waitlist_email_key unique (email)
) TABLESPACE pg_default;