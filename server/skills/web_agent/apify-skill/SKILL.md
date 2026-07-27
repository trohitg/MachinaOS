---
name: apify-skill
description: Run web scrapers and extract data from websites and social media platforms using Apify actors. Supports Instagram, TikTok, Twitter/X, LinkedIn, Facebook, YouTube, Google Search, and general web crawling.
allowed-tools: "apify_actor"
metadata:
  author: opencompany
  version: "1.0"
  category: web

---

# Apify Web Scraping Skill

Run pre-built web scrapers (Actors) to extract data from websites and social media platforms.

## How It Works

This skill provides instructions for the **Apify Actor** tool node. Connect the **Apify Actor** node to Zeenie's `input-tools` handle to enable web scraping capabilities.

## apify_run_actor Tool

Run any Apify actor and retrieve scraped results.

### Schema Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| actor_id | string | Yes | Actor ID from Apify Store (e.g., `apify/instagram-scraper`) |
| actor_input | object or JSON string | No | Actor input merged with preset fields (default: `{}`) |
| max_results | integer | No | Maximum items to return (default: 100) |
| max_total_charge_usd | number | No | Optional whole-run spending cap in USD |

### Popular Actors

| Platform | Actor ID | Use Case |
|----------|----------|----------|
| Instagram | `apify/instagram-scraper` | Profiles, posts, hashtags, comments |
| TikTok | `clockworks/tiktok-scraper` | Videos, profiles, trends, hashtags |
| Twitter/X | `apidojo/tweet-scraper` | Tweets, profiles, search results |
| X posts | [`xquik/x-tweet-scraper`](https://apify.com/xquik/x-tweet-scraper) | Search, timelines, tweets, threads, replies, quotes |
| X audiences | [`xquik/x-follower-scraper`](https://apify.com/xquik/x-follower-scraper) | Followers, following, lists, communities, overlap |
| LinkedIn | `curious_coder/linkedin-profile-scraper` | Profiles, companies |
| Facebook | `apify/facebook-posts-scraper` | Posts, pages, groups |
| YouTube | `apify/youtube-scraper` | Videos, channels, comments |
| Google Search | `apify/google-search-scraper` | SERP results, organic listings |
| Google Maps | `apify/google-maps-scraper` | Places, reviews, business info |
| Web Crawler | `apify/website-content-crawler` | Any website content |
| Web Scraper | `apify/web-scraper` | Custom scraping with selectors |

### Response Format

```json
{
  "run_id": "abc123xyz",
  "actor_id": "apify/instagram-scraper",
  "status": "SUCCEEDED",
  "items": [
    { "id": "123", "text": "Post content...", "likes": 500 }
  ],
  "item_count": 50,
  "dataset_id": "dataset-id-here",
  "compute_units": 0.5,
  "started_at": "2026-02-23T10:00:00Z",
  "finished_at": "2026-02-23T10:02:30Z"
}
```

### Examples

**Scrape Instagram profile:**
```json
{
  "actor_id": "apify/instagram-scraper",
  "actor_input": {"directUrls": ["https://instagram.com/natgeo"], "resultsLimit": 50},
  "max_results": 50
}
```

**Search TikTok hashtag:**
```json
{
  "actor_id": "clockworks/tiktok-scraper",
  "actor_input": {"hashtags": ["trending", "fyp"], "resultsPerPage": 30},
  "max_results": 30
}
```

**Search Twitter/X:**
```json
{
  "actor_id": "apidojo/tweet-scraper",
  "actor_input": {"searchTerms": ["AI automation"], "maxItems": 100},
  "max_results": 100
}
```

**Search X with Xquik:**
```json
{
  "actor_id": "xquik/x-tweet-scraper",
  "actor_input": {
    "mode": "search",
    "searchTerms": ["AI automation", "#buildinpublic"],
    "maxItems": 100,
    "outputVariant": "rich"
  },
  "max_results": 100
}
```

**Compare X audiences with Xquik:**
```json
{
  "actor_id": "xquik/x-follower-scraper",
  "actor_input": {
    "twitterHandles": ["openai", "nasa"],
    "relation": "followers",
    "maxItems": 200,
    "maxItemsPerTarget": 100,
    "overlapMode": true
  },
  "max_results": 200
}
```

**Google Search:**
```json
{
  "actor_id": "apify/google-search-scraper",
  "actor_input": {"queries": "best AI tools 2026", "maxPagesPerQuery": 3},
  "max_results": 30
}
```

**Crawl website content:**
```json
{
  "actor_id": "apify/website-content-crawler",
  "actor_input": {
    "startUrls": [{"url": "https://docs.example.com"}],
    "maxCrawlDepth": 2,
    "maxCrawlPages": 50
  },
  "max_results": 50
}
```

**Scrape Google Maps places:**
```json
{
  "actor_id": "apify/google-maps-scraper",
  "actor_input": {
    "searchStringsArray": ["restaurants in San Francisco"],
    "maxCrawledPlaces": 20
  },
  "max_results": 20
}
```

## Common Input Parameters by Actor

### Instagram Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| directUrls | array | Instagram URLs to scrape |
| resultsLimit | number | Max results per URL (1-1000) |
| maxComments | number | Comments per post (0-100) |
| searchType | string | Type of search: `hashtag`, `user`, `place` |

### TikTok Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| profiles | array | TikTok usernames to scrape |
| hashtags | array | Hashtags to scrape (without #) |
| resultsPerPage | number | Results per request |

### Twitter/X Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| searchTerms | array | Search queries or hashtags |
| twitterHandles | array | Usernames (without @) |
| maxItems | number | Maximum tweets to fetch |

### Xquik X Tweet Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| mode | string | Route such as `search`, `profileTweets`, `thread`, or `replies` |
| searchTerms | array | Run several X searches in one Actor run |
| twitterHandles | array | Collect timelines for X handles |
| maxItems | number | Cap results across the whole run |
| maxItemsPerTarget | number | Optionally cap each explicit target |
| outputVariant | string | Return `legacy`, `rich`, or `raw` results |

### Xquik X Follower Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| twitterHandles | array | X handles to inspect |
| relation | string | Collect `followers`, `following`, or `verified_followers` |
| maxItems | number | Cap results across the whole run |
| maxItemsPerTarget | number | Optionally cap each target |
| outputMode | string | Return `compact`, `full`, or `raw` profiles |
| overlapMode | boolean | Merge duplicate profiles and report audience overlap |

### Google Search Scraper
| Parameter | Type | Description |
|-----------|------|-------------|
| queries | string | Search query |
| maxPagesPerQuery | number | Pages to scrape (10 results/page) |
| languageCode | string | Language filter (e.g., `en`) |
| countryCode | string | Country filter (e.g., `us`) |

### Website Content Crawler
| Parameter | Type | Description |
|-----------|------|-------------|
| startUrls | array | URLs to crawl from (objects with `url` key) |
| maxCrawlDepth | number | Link depth (0 = start URLs only) |
| maxCrawlPages | number | Total pages limit |

## Error Responses

**Actor not found:**
```json
{
  "success": false,
  "error": "Actor 'invalid/actor-id' not found"
}
```

**Timeout:**
```json
{
  "success": false,
  "error": "Actor run timed out after 300 seconds"
}
```

**Run failed:**
```json
{
  "success": false,
  "error": "Actor run failed with status FAILED"
}
```

## Run Status Values

| Status | Meaning |
|--------|---------|
| SUCCEEDED | Run completed successfully |
| FAILED | Run encountered an error |
| ABORTED | Run was manually stopped |
| TIMED-OUT | Run exceeded timeout limit |
| RUNNING | Run still in progress |

## Use Cases

| Use Case | Actor | Description |
|----------|-------|-------------|
| Social listening | tweet-scraper | Monitor brand mentions |
| Competitor research | instagram-scraper | Analyze competitor posts |
| Lead generation | linkedin-profile-scraper | Extract business contacts |
| SEO research | google-search-scraper | Analyze SERP rankings |
| Content aggregation | website-content-crawler | Collect articles from sites |
| Price monitoring | web-scraper | Track product prices |
| Review analysis | google-maps-scraper | Gather customer reviews |

## Guidelines

1. **Actor IDs**: Use format `username/actor-name` from Apify Store
2. **Input JSON**: Must be valid JSON string with actor-specific parameters
3. **Timeouts**: Default 300 seconds, configurable on the node
4. **Max Results**: Limits items returned (not items scraped)
5. **Memory**: Higher memory = faster execution, higher cost

## Pricing Notes

Pricing differs by Actor and can change. Check the Actor's current Apify Store
pricing before every large run. Set explicit result limits in Actor input and
use `max_total_charge_usd` for a whole-run spending cap.

## Setup Requirements

1. Connect the **Apify Actor** node to Zeenie's `input-tools` handle
2. Configure your Apify API token in Credentials Modal
3. Select an actor or enter custom actor ID
4. Provide actor-specific input as JSON

## Security Notes

1. Respect website terms of service
2. Use reasonable scraping rates to avoid IP bans
3. Don't scrape personal data without consent
4. Store scraped data securely
5. Comply with GDPR and data protection laws
6. Confirm scope and cost before starting paid Actor runs

Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.
