"""Actor-specific input normalization for the Apify node."""

from __future__ import annotations

import json
from typing import Any


def _comma_separated(value: str) -> list[str]:
    """Return trimmed, non-empty values from a comma-separated field."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_actor_input(parameters: dict[str, Any]) -> dict[str, Any]:
    """Merge preset helpers into raw Actor input.

    Apify Actors expect camelCase input keys. Node parameters use snake_case,
    so this function translates only the preset helpers that users filled.
    Raw Actor input remains available for every schema field.
    """
    actor_id = parameters.get("actor_id", "")
    if actor_id == "custom":
        actor_id = parameters.get("custom_actor_id", "")

    actor_input = parameters.get("actor_input", {})
    if isinstance(actor_input, str):
        try:
            actor_input = json.loads(actor_input) if actor_input.strip() else {}
        except json.JSONDecodeError:
            actor_input = {}
    elif not isinstance(actor_input, dict):
        actor_input = {}

    if actor_id == "apify/instagram-scraper":
        if urls := parameters.get("instagram_urls", ""):
            actor_input["directUrls"] = _comma_separated(urls)
    elif actor_id == "clockworks/tiktok-scraper":
        if profiles := parameters.get("tiktok_profiles", ""):
            actor_input["profiles"] = _comma_separated(profiles)
        if hashtags := parameters.get("tiktok_hashtags", ""):
            actor_input["hashtags"] = _comma_separated(hashtags)
    elif actor_id in {"apidojo/tweet-scraper", "xquik/x-tweet-scraper"}:
        if search_terms := parameters.get("twitter_search_terms", ""):
            actor_input["searchTerms"] = _comma_separated(search_terms)
        if handles := parameters.get("twitter_handles", ""):
            actor_input["twitterHandles"] = _comma_separated(handles)
        if actor_id == "xquik/x-tweet-scraper":
            if mode := parameters.get("xquik_tweet_mode"):
                actor_input["mode"] = mode
            if output_variant := parameters.get("xquik_tweet_output_variant"):
                actor_input["outputVariant"] = output_variant
    elif actor_id == "xquik/x-follower-scraper":
        if handles := parameters.get("twitter_handles", ""):
            actor_input["twitterHandles"] = _comma_separated(handles)
        if relation := parameters.get("xquik_follower_relation"):
            actor_input["relation"] = relation
        if output_mode := parameters.get("xquik_follower_output_mode"):
            actor_input["outputMode"] = output_mode
        if parameters.get("xquik_overlap_mode"):
            actor_input["overlapMode"] = True
    elif actor_id == "apify/google-search-scraper":
        if query := parameters.get("google_search_query", ""):
            actor_input["searchQuery"] = query
            actor_input["maxPagesPerQuery"] = parameters.get("google_search_pages", 1)
    elif actor_id == "apify/website-content-crawler" and (start_urls := parameters.get("crawler_start_urls", "")):
        actor_input["startUrls"] = [{"url": url} for url in _comma_separated(start_urls)]
        actor_input["maxCrawlDepth"] = parameters.get("crawler_max_depth", 2)
        actor_input["maxCrawlPages"] = parameters.get("crawler_max_pages", 50)

    is_xquik_actor = actor_id in {"xquik/x-tweet-scraper", "xquik/x-follower-scraper"}
    if is_xquik_actor and (max_items := parameters.get("xquik_max_items")) is not None:
        actor_input["maxItems"] = max_items
    if is_xquik_actor and (max_items_per_target := parameters.get("xquik_max_items_per_target")) is not None:
        actor_input["maxItemsPerTarget"] = max_items_per_target

    return actor_input
