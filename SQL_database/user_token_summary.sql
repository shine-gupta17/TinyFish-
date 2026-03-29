create view public.user_token_summary as
select
  up.provider_id,
  up.email,
  up.full_name,
  COALESCE(tokens.total_purchased, 0::bigint) as total_tokens_purchased,
  COALESCE(tokens.total_consumed, 0::bigint) as total_tokens_consumed,
  COALESCE(tokens.total_remaining, 0::bigint) as total_tokens_remaining,
  COALESCE(tokens.subscription_tokens, 0::bigint) as subscription_tokens,
  COALESCE(tokens.package_tokens, 0::bigint) as package_tokens
from
  user_profiles up
  left join lateral get_user_total_tokens (up.provider_id) tokens (
    total_purchased,
    total_consumed,
    total_remaining,
    subscription_tokens,
    package_tokens
  ) on true;