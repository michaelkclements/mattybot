"""
MattyBot configuration.

Add quotes to QUOTES and set QUOTE_TIMES to control when they post.
CHANNEL_ID is the Discord channel the quotes are sent to.
"""

import datetime

# ── Channel ───────────────────────────────────────────────────────────────────
# ID of the channel where quotes will be posted.
# Set this in .env as CHANNEL_ID, or hardcode it here.
CHANNEL_ID: int = 0  # overridden by .env

# ── Activity detection ─────────────────────────────────────────────────────
# Number of seconds to look back when counting message activity.
MESSAGE_WINDOW: int = 600  # 10 minutes

# Messages within MESSAGE_WINDOW needed to be considered "busy".
BUSY_THRESHOLD: int = 10

# When busy, probability (0–1) of posting a quote after each message.
# 0.05 = roughly 1 quote per 20 messages.
BUSY_QUOTE_CHANCE: float = 0.0025

# ── Quotes ──────────────────────────────────────────────────────────────
# Add Matty's quotes here.
# REPLY_QUOTES are used when MattyBot replies to someone in a busy chat.
# STANDALONE_QUOTES are used for quiet fallback posts.
# Both lists can be the same — just copy your quotes into each.
REPLY_QUOTES: list[str] = [
    # Add Matty's quotes here
]

STANDALONE_QUOTES: list[str] = REPLY_QUOTES

# ── Link conversion ────────────────────────────────────────────────────────
# Domains to rewrite when spotted in messages.
# Maps source domain → replacement domain.
LINK_REWRITES: dict[str, str] = {
    "x.com": "xcancel.com",
}
