#!/usr/bin/env python3
"""
RateCard API — instant brand-deal price estimates for creators.
Zero dependencies. Run:  python3 server.py [port]
Serves the JSON API, the landing page, legal pages, icon, and OpenAPI spec.
"""
import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Pricing data -----------------------------------------------------------
# base rate: $ per 1,000 followers for an Instagram feed post.
# Calibrated against published 2026 influencer rate benchmarks (see SPEC.md).
NICHES = {
    "finance":       {"name": "Finance & Investing",   "base_per_1k": 60},
    "tech":          {"name": "Tech & Gadgets",        "base_per_1k": 70},
    "business":      {"name": "Business & B2B",        "base_per_1k": 90},
    "fitness":       {"name": "Fitness & Health",      "base_per_1k": 45},
    "beauty":        {"name": "Beauty & Skincare",     "base_per_1k": 37},
    "food":          {"name": "Food & Cooking",        "base_per_1k": 37},
    "travel":        {"name": "Travel",                "base_per_1k": 30},
    "lifestyle":     {"name": "Lifestyle",             "base_per_1k": 18},
    "gaming":        {"name": "Gaming",                "base_per_1k": 15},
    "education":     {"name": "Education",             "base_per_1k": 40},
    "entertainment": {"name": "Entertainment & Memes", "base_per_1k": 10},
}

PLATFORMS = {
    "instagram": {"name": "Instagram",  "multiplier": 1.0},
    "tiktok":    {"name": "TikTok",     "multiplier": 0.85},
    "youtube":   {"name": "YouTube",    "multiplier": 2.5},
    "x":         {"name": "X (Twitter)","multiplier": 0.6},
}

CONTENT_TYPES = {
    "post":        {"name": "Feed post",                 "multiplier": 1.0},
    "short_video": {"name": "Short video (Reel/TikTok)", "multiplier": 1.4},
    "story":       {"name": "Story set",                 "multiplier": 0.45},
    "long_video":  {"name": "Long-form video",           "multiplier": 2.2},
}

# (follower cap, typical engagement %) — used only if caller supplies engagement
TIER_ENGAGEMENT = [
    (10_000, 6.0),
    (100_000, 4.0),
    (500_000, 2.5),
    (1_000_000, 1.8),
    (float("inf"), 1.2),
]

TIPS = [
    "Short video earns 50-100% more than a static post — lead with video.",
    "Quote the high end of your range first; brands expect negotiation.",
    "Charge +50% if the brand wants 90-day paid ad usage rights.",
    "Bundle deals (post + stories + reel) close faster than one-off posts.",
    "High engagement beats high follower count — small engaged accounts can charge up.",
]


def tier_for(followers):
    if followers < 10_000:
        return "nano"
    if followers < 100_000:
        return "micro"
    if followers < 500_000:
        return "mid-tier"
    if followers < 1_000_000:
        return "macro"
    return "mega"


def typical_engagement(followers):
    for cap, rate in TIER_ENGAGEMENT:
        if followers < cap:
            return rate
    return 1.2


def price_estimate(niche, followers, platform, content_type, engagement_rate=None):
    base = NICHES[niche]["base_per_1k"]
    plat_mult = PLATFORMS[platform]["multiplier"]
    cont_mult = CONTENT_TYPES[content_type]["multiplier"]
    eng_mult = 1.0
    if engagement_rate is not None:
        typical = typical_engagement(followers)
        eng_mult = max(0.6, min(1.6, 0.75 + 0.25 * (engagement_rate / typical)))
    mid = base * (followers / 1000) ** 0.9 * plat_mult * cont_mult * eng_mult
    mid = int(round(mid))
    return {
        "low": int(round(mid * 0.7)),
        "mid": mid,
        "high": int(round(mid * 1.3)),
        "engagement_multiplier": round(eng_mult, 3),
    }


def build_response(niche, followers, platform, content_type, engagement_rate=None):
    est = price_estimate(niche, followers, platform, content_type, engagement_rate)
    mid = est["mid"]
    add_ons = {
        "usage_rights_90d": {
            "label": "+50% — 90-day paid ad usage rights",
            "low": int(round(mid * 1.5 * 0.7)),
            "high": int(round(mid * 1.5 * 1.3)),
        },
        "exclusivity_6mo": {
            "label": "+100% — 6-month category exclusivity",
            "low": int(round(mid * 2.0 * 0.7)),
            "high": int(round(mid * 2.0 * 1.3)),
        },
    }
    return {
        "currency": "USD",
        "estimate": {"low": est["low"], "mid": mid, "high": est["high"]},
        "tier": tier_for(followers),
        "inputs": {
            "niche": niche,
            "followers": followers,
            "platform": platform,
            "content_type": content_type,
            "engagement_rate": engagement_rate,
        },
        "breakdown": {
            "base_per_1k": NICHES[niche]["base_per_1k"],
            "platform_multiplier": PLATFORMS[platform]["multiplier"],
            "content_multiplier": CONTENT_TYPES[content_type]["multiplier"],
            "engagement_multiplier": est["engagement_multiplier"],
        },
        "add_ons": add_ons,
        "tips": TIPS[:3],
        "disclaimer": (
            "Estimate based on 2026 public influencer rate benchmarks. "
            "Actual deals vary with engagement, audience quality, usage rights, and negotiation."
        ),
    }


# --- HTTP layer ---------------------------------------------------------------

STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/privacy": ("privacy.html", "text/html"),
    "/terms": ("terms.html", "text/html"),
    "/icon.png": ("icon.png", "image/png"),
    "/openapi.json": ("openapi.json", "application/json"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "RateCard/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_file(self, filename, content_type):
        path = os.path.join(BASE_DIR, filename)
        if not os.path.isfile(path):
            self._send_json({"error": "not found"}, 404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", content_type + "; charset=utf-8"
                        if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in STATIC_FILES:
            filename, ctype = STATIC_FILES[path]
            self._send_file(filename, ctype)
            return
        if path == "/api/health":
            self._send_json({"ok": True, "service": "ratecard", "version": "1.0"})
            return
        if path == "/api/niches":
            self._send_json({"niches": [
                {"id": k, **v} for k, v in NICHES.items()]})
            return
        if path == "/api/platforms":
            self._send_json({"platforms": [
                {"id": k, **v} for k, v in PLATFORMS.items()]})
            return
        if path == "/api/content-types":
            self._send_json({"content_types": [
                {"id": k, **v} for k, v in CONTENT_TYPES.items()]})
            return
        self._send_json({"error": "not found"}, 404)

    def do_HEAD(self):  # uptime monitors often probe with HEAD
        self.do_GET()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/price":
            self._send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "request body must be JSON"}, 400)
            return

        niche = data.get("niche")
        platform = data.get("platform", "instagram")
        content_type = data.get("content_type", "post")
        followers = data.get("followers")
        engagement = data.get("engagement_rate")

        if niche not in NICHES:
            self._send_json({"error": f"unknown niche '{niche}'. "
                                      f"Valid: {sorted(NICHES)}"}, 400)
            return
        if platform not in PLATFORMS:
            self._send_json({"error": f"unknown platform '{platform}'. "
                                      f"Valid: {sorted(PLATFORMS)}"}, 400)
            return
        if content_type not in CONTENT_TYPES:
            self._send_json({"error": f"unknown content_type '{content_type}'. "
                                      f"Valid: {sorted(CONTENT_TYPES)}"}, 400)
            return
        if not isinstance(followers, (int, float)) or not 1_000 <= followers <= 100_000_000:
            self._send_json({"error": "followers must be a number between 1000 and 100000000"}, 400)
            return
        if engagement is not None and (
                not isinstance(engagement, (int, float)) or not 0.1 <= engagement <= 30):
            self._send_json({"error": "engagement_rate must be a percent between 0.1 and 30"}, 400)
            return

        resp = build_response(niche, int(followers), platform, content_type, engagement)
        self._send_json(resp)

    def log_message(self, fmt, *args):  # quieter logs
        pass


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"RateCard serving on port {port}  (dir: {BASE_DIR})")
    srv.serve_forever()
