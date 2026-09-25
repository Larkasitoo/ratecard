# RateCard — SPEC

**Concept:** A brand-deal pricing calculator for creators. Ask Muse "what should I charge
for a sponsored post?" with a niche + follower count, get an instant price range.
One job, done well. Free, no login, no payments in v1.

**Why this first:** zero running costs (pure math, no AI key), no auth, no payments —
almost nothing for Meta's review to choke on. Example prompts write themselves.
Audience = creators trying to make money (the user's target market).

## Pricing model

```
mid = niche_base_per_1k × (followers / 1000) ^ 0.9 × platform_mult × content_mult × engagement_mult
low  = mid × 0.7
high = mid × 1.3
```

- Sub-linear follower scaling (0.9 exponent): mega accounts earn more per deal but
  less per follower — matches market reality.
- ±30% band: published 2026 benchmarks disagree 2–3x, so we present a range, not
  a false-precise number.

### Niche base rates ($ per 1k followers, Instagram feed-post baseline)

Calibrated so a 50K-follower Instagram post lands inside published 2026 ranges:

| niche         | base/1k | 50K IG post → mid | published 2026 range (50K) |
|---------------|---------|-------------------|----------------------------|
| finance       | 60      | ~$2,030           | $1,000–$3,000              |
| tech          | 70      | ~$2,370           | $2,000–$5,000 (75K)        |
| business      | 90      | ~$3,040           | $1,500–$5,000 (25K)        |
| fitness       | 45      | ~$1,520           | $750–$2,500                |
| beauty        | 37      | ~$1,250           | $500–$2,000                |
| food          | 37      | ~$1,250           | $500–$2,000                |
| travel        | 30      | ~$1,010           | ~$800–$2,000               |
| lifestyle     | 18      | ~$610             | $250–$1,000                |
| gaming        | 15      | ~$510             | $200–$800                  |
| education     | 40      | ~$1,350           | n/a (mid-premium)          |
| entertainment | 10      | ~$340             | $150–$500                  |

Sources: socialrails.com, influencerfee.com, earnifyhub.com, starngage.com
(September 2026 reads).

### Platform multipliers (Instagram = 1.0 baseline)

| platform  | mult | rationale                              |
|-----------|------|----------------------------------------|
| instagram | 1.0  | baseline                               |
| tiktok    | 0.85 | rates run 15–40% below IG, gap closing |
| youtube   | 2.5  | long-form commands highest rates       |
| x         | 0.6  | X/Twitter runs lower                   |

### Content-type multipliers

| content_type | mult | rationale                          |
|--------------|------|------------------------------------|
| post         | 1.0  | feed post / standard               |
| short_video  | 1.4  | Reels 50–100% above static posts   |
| story        | 0.45 | stories 40–60% cheaper             |
| long_video   | 2.2  | dedicated long-form premium        |

### Engagement adjustment (optional input)

Typical engagement by tier: nano 6%, micro 4%, mid-tier 2.5%, macro 1.8%, mega 1.2%.
`engagement_mult = clamp(0.75 + 0.25 × (given / typical), 0.6, 1.6)`.
Rewards high-engagement small accounts — the #1 factor brands actually pay for.

### Add-ons (shown alongside every estimate)

- 90-day paid ad usage rights: +50% of mid
- 6-month category exclusivity: +100% of mid

## API

Base URL: `https://<host>/api`

| Method | Path                 | Description                              |
|--------|----------------------|------------------------------------------|
| GET    | /api/health          | `{ok: true}`                             |
| GET    | /api/niches          | list of niches + base rates              |
| GET    | /api/platforms       | list of platforms + multipliers          |
| GET    | /api/content-types   | list of content types + multipliers      |
| POST   | /api/price           | price estimate (see below)               |

`POST /api/price` body:
```json
{
  "niche": "fitness",
  "followers": 50000,
  "platform": "instagram",
  "content_type": "short_video",
  "engagement_rate": 4.2
}
```
`engagement_rate` optional (percent, e.g. 4.2 = 4.2%).

Response:
```json
{
  "currency": "USD",
  "estimate": {"low": 1490, "mid": 2130, "high": 2770},
  "tier": "micro",
  "inputs": {"niche": "fitness", "followers": 50000, "platform": "instagram",
             "content_type": "short_video", "engagement_rate": 4.2},
  "breakdown": {"base_per_1k": 45, "platform_multiplier": 1.0,
                "content_multiplier": 1.4, "engagement_multiplier": 1.04},
  "add_ons": {
    "usage_rights_90d": {"label": "+50% · 90-day paid ad usage", "low": 2240, "high": 4160},
    "exclusivity_6mo": {"label": "+100% · 6-month category exclusivity", "low": 2980, "high": 5540}
  },
  "tips": ["Reels earn 50-100% more than static posts — lead with video.",
           "Quote the high end first; brands expect negotiation."],
  "disclaimer": "Estimate from 2026 public rate benchmarks. Actual deals vary with engagement, audience quality, usage rights, and negotiation."
}
```

Validation: followers 1,000–100,000,000; niche/platform/content_type must be known;
engagement_rate 0.1–30. Errors return `400 {"error": "..."}`.

## Site

- `GET /` — landing page with live calculator demo (calls the API in-browser)
- `GET /privacy` — privacy policy (we store nothing, no accounts, no cookies)
- `GET /terms` — terms of service (estimates are informational, not financial advice)
- `GET /icon.png` — 512×512 connector icon
- `GET /openapi.json` — OpenAPI 3.0 spec (for the "Raw API" submission path)

## Connector submission mapping (muse.ai/platform)

- Connection type: **Raw API** (+ openapi.json)
- Auth: none (checkboxes left unchecked)
- Payments: "does not accept payments" (v1)
- Example prompts:
  1. "How much should a fitness creator with 50k Instagram followers charge for a sponsored post?"
  2. "Price a 90-second TikTok for a beauty creator with 120k followers and 5% engagement."
  3. "What should I charge for a dedicated YouTube video? I do tech reviews, 300k subscribers."
- Needs before submitting: public URL (free hosting), work/company email,
  product website (this page), privacy + terms URLs (this site).

## Files

```
~/workspace/ratecard/
  SPEC.md          this file
  server.py        zero-dependency Python API + static server
  index.html       landing page
  privacy.html     privacy policy
  terms.html       terms of service
  openapi.json     OpenAPI 3.0 spec
  icon.png         512×512 connector icon
```

## Deploy (free)

Any of: Vercel / Render / Railway / Cloudflare Workers (needs small adapter) /
any VPS with Python 3. Run: `python3 server.py` (default port 8000, `PORT` env aware).

## v2 ideas (after listing)

- Stripe Link payments: "pro" PDF rate cards, historical tracking
- UGC-only pricing mode (content without posting: −30–50%)
- Retainer/ambassadorship estimator
