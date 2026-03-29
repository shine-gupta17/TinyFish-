create view public.active_user_subscriptions as
select
  provider_id,
  dodo_subscription_id,
  plan_type,
  status,
  tokens_allocated,
  tokens_consumed,
  tokens_remaining,
  amount,
  currency,
  next_billing_date,
  created_at
from
  dodo_subscriptions ds
where
  status = any (array['active'::text, 'on_hold'::text])
order by
  created_at desc;