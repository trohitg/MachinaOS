"""Parameter schema for the Apify Actor node."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApifyActorParams(BaseModel):
    actor_id: Literal[
        "apify/instagram-scraper",
        "clockworks/tiktok-scraper",
        "apidojo/tweet-scraper",
        "xquik/x-tweet-scraper",
        "xquik/x-follower-scraper",
        "apify/linkedin-scraper",
        "apify/facebook-pages-scraper",
        "streamers/youtube-scraper",
        "apify/google-search-scraper",
        "compass/crawler-google-places",
        "apify/website-content-crawler",
        "curious_coder/web-scraper",
        "custom",
    ] = Field(
        default="apify/instagram-scraper",
        description="Actor preset. Pick 'custom' to enter a specific actor ID.",
    )
    custom_actor_id: str = Field(
        default="",
        description="Custom actor ID (e.g. username/actor-name).",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["custom"]}}},
    )
    actor_input: Any = Field(
        default_factory=dict,
        description="Raw JSON input passed to the Actor and merged with preset fields.",
        json_schema_extra={"rows": 6},
    )

    instagram_urls: str = Field(
        default="",
        description="Comma-separated Instagram URLs.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/instagram-scraper"]}}},
    )
    tiktok_profiles: str = Field(
        default="",
        description="Comma-separated TikTok profile handles.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["clockworks/tiktok-scraper"]}}},
    )
    tiktok_hashtags: str = Field(
        default="",
        description="Comma-separated TikTok hashtags.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["clockworks/tiktok-scraper"]}}},
    )
    twitter_search_terms: str = Field(
        default="",
        description="Comma-separated X search terms.",
        json_schema_extra={
            "displayOptions": {
                "show": {"actor_id": ["apidojo/tweet-scraper", "xquik/x-tweet-scraper"]},
            },
        },
    )
    twitter_handles: str = Field(
        default="",
        description="Comma-separated X handles, with or without @.",
        json_schema_extra={
            "displayOptions": {
                "show": {
                    "actor_id": [
                        "apidojo/tweet-scraper",
                        "xquik/x-tweet-scraper",
                        "xquik/x-follower-scraper",
                    ],
                },
            },
        },
    )
    xquik_tweet_mode: (
        Literal[
            "legacy",
            "tweet",
            "tweets",
            "search",
            "profileTweets",
            "profileReplies",
            "profileMedia",
            "profileLikes",
            "listTweets",
            "article",
            "replies",
            "quotes",
            "thread",
            "retweeters",
            "favoriters",
        ]
        | None
    ) = Field(
        default=None,
        description="Optional Xquik route. Leave empty to infer it from the input.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["xquik/x-tweet-scraper"]}}},
    )
    xquik_tweet_output_variant: Literal["legacy", "rich", "raw"] | None = Field(
        default=None,
        description="Optional Xquik tweet result detail level.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["xquik/x-tweet-scraper"]}}},
    )
    xquik_follower_relation: (
        Literal[
            "followers",
            "following",
            "verified_followers",
            "list_members",
            "list_followers",
            "community_members",
        ]
        | None
    ) = Field(
        default=None,
        description="Optional X relation. Leave empty to collect followers.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["xquik/x-follower-scraper"]}}},
    )
    xquik_follower_output_mode: Literal["compact", "full", "raw"] | None = Field(
        default=None,
        description="Optional Xquik profile result detail level.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["xquik/x-follower-scraper"]}}},
    )
    xquik_overlap_mode: bool = Field(
        default=False,
        description="Merge duplicate profiles and report audience overlap.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["xquik/x-follower-scraper"]}}},
    )
    xquik_max_items: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Optional result cap across the whole Xquik run.",
        json_schema_extra={
            "displayOptions": {
                "show": {
                    "actor_id": ["xquik/x-tweet-scraper", "xquik/x-follower-scraper"],
                },
            },
        },
    )
    xquik_max_items_per_target: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Optional Xquik result cap for each target.",
        json_schema_extra={
            "displayOptions": {
                "show": {
                    "actor_id": ["xquik/x-tweet-scraper", "xquik/x-follower-scraper"],
                },
            },
        },
    )
    google_search_query: str = Field(
        default="",
        description="Google search query.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/google-search-scraper"]}}},
    )
    google_search_pages: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Max pages per query.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/google-search-scraper"]}}},
    )
    crawler_start_urls: str = Field(
        default="",
        description="Comma-separated start URLs.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/website-content-crawler"]}}},
    )
    crawler_max_depth: int = Field(
        default=2,
        ge=0,
        le=20,
        description="Max crawl depth.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/website-content-crawler"]}}},
    )
    crawler_max_pages: int = Field(
        default=50,
        ge=1,
        le=10000,
        description="Max pages to crawl.",
        json_schema_extra={"displayOptions": {"show": {"actor_id": ["apify/website-content-crawler"]}}},
    )

    max_results: int = Field(default=100, ge=1, le=10000)
    timeout: int = Field(default=300, ge=1, le=3600)
    max_total_charge_usd: float | None = Field(
        default=None,
        gt=0,
        description="Optional whole-run spending cap in USD.",
    )
    memory: Literal[128, 256, 512, 1024, 2048, 4096, 8192] = Field(
        default=1024,
        description="Actor memory in MB.",
    )

    model_config = ConfigDict(extra="ignore")
