create table public.hackathon_registrations (
  id serial not null,
  registration_id uuid not null default extensions.uuid_generate_v4(),
  provider_id text not null,
  full_name text not null,
  email text not null,
  phone_number text null,
  college_name text not null,
  college_email text null,
  major text null,
  graduation_year integer null,
  linkedin_profile text null,
  github_profile text null,
  team_name text null,
  team_member_emails text[] null default array[]::text[],
  skills text[] null default array[]::text[],
  idea_summary text null,
  experience_level text null default 'Beginner'::text,
  dietary_restrictions text null,
  registration_status text not null default 'confirmed'::text,
  metadata jsonb null default '{}'::jsonb,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),

  constraint hackathon_registrations_pkey primary key (registration_id),
  constraint hackathon_registrations_id_key unique (id),

  constraint hackathon_registrations_provider_id_fkey
    foreign key (provider_id)
    references user_profiles (provider_id)
    on delete cascade,

  constraint hackathon_registrations_registration_status_check
    check (
      registration_status = any (
        array[
          'pending'::text,
          'confirmed'::text,
          'checked_in'::text,
          'cancelled'::text
        ]
      )
    )
) tablespace pg_default;

create unique index if not exists unique_user_hackathon_registration
on public.hackathon_registrations using btree (provider_id)
tablespace pg_default;

create index if not exists idx_hackathon_registrations_email
on public.hackathon_registrations using btree (email)
tablespace pg_default;

create index if not exists idx_hackathon_registrations_created_at
on public.hackathon_registrations using btree (created_at)
tablespace pg_default;

create index if not exists idx_hackathon_registrations_status
on public.hackathon_registrations using btree (registration_status)
tablespace pg_default;

create trigger update_hackathon_registrations_updated_at
before update on hackathon_registrations
for each row
execute function update_updated_at_column();