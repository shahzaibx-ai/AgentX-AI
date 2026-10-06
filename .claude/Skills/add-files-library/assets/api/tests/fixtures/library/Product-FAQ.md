# Acme API: product FAQ

## Rate limits
Each API key may make 600 requests per minute. Responses include the
X-RateLimit-Remaining and X-RateLimit-Reset headers. A 429 response means you
should wait until the reset time and retry.

## Plans and pricing
Starter costs $19 per user per month and Team costs $39 per user per month.
Enterprise is priced on request. Annual billing gives two months free.

## Single sign-on
SAML single sign-on is included in the Team and Enterprise plans. It is not
available on Starter.

## Data retention
Request logs are kept for 90 days, then deleted. Enterprise customers can choose
a retention period between 30 and 365 days.
