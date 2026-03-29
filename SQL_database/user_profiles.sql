create table public.user_profiles (
  id serial not null,
  provider_id text not null,
  auth_provider text not null,
  email text null,
  phone_number text null,
  password text null,
  full_name text null,
  username text null,
  profile_picture text null,
  is_verified boolean null default false,
  created_at timestamp with time zone null default timezone ('utc'::text, now()),
  updated_at timestamp with time zone null default timezone ('utc'::text, now()),
  constraint user_profiles_pkey primary key (provider_id),
  constraint user_profiles_email_key unique (email),
  constraint user_profiles_id_key unique (id),
  constraint user_profiles_phone_number_key unique (phone_number)
) TABLESPACE pg_default;