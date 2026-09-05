---
name: tikhub-skill
description: Scrape TikTok, Douyin, Instagram, YouTube, Twitter/X, Xiaohongshu, Bilibili, Kuaishou, Weibo, Reddit, Threads, LinkedIn and more through the TikHub pay-per-request API - discover endpoints, call them by id, parse any share URL, and check account balance.
allowed-tools: "tikhub_action"
metadata:
  author: opencompany
  version: "1.0"
  category: web

---

# TikHub Skill

TikHub (api.tikhub.io) is a pay-per-request REST API that exposes roughly
1,000 scraping endpoints across TikTok, Douyin, Instagram, YouTube,
Twitter/X, Xiaohongshu, Bilibili, Kuaishou, Weibo, Reddit, Threads,
LinkedIn, Zhihu, Lemon8 and others. Each endpoint is one HTTP call that
returns the platform's raw data; there are no long-running jobs, no
actors, no datasets to poll. The `tikhub_action` tool is a thin, flattened
wrapper over the official `tikhub` Python SDK: every SDK method is
addressable by its resource-dot-method id (for example
`douyin_web.fetch_one_video`), and the tool passes your `params` straight
through as the SDK's keyword arguments.

## Tool: tikhub_action

### Operations

| Operation | Purpose | Key fields |
|---|---|---|
| `list_endpoints` | Discover endpoints (no API call, free) - returns each endpoint's id, HTTP method, path, summary and typed params with `required` flags | `platform` (default `all`), `search` (substring over id / summary / path), `limit` |
| `call` | Invoke one endpoint by id | `endpoint` (resource-dot-method id or a `/api/v1/...` path), `params` (JSON object of the SDK keyword args) |
| `fetch_url` | Parse any TikTok / Douyin share URL through `hybrid_parsing.video_data` | `url`, `minimal` (trimmed payload) |
| `account` | Balance, free credit and today's usage for the stored key | - |

### Response

`call` and `fetch_url`:

```json
{
  "operation": "call",
  "endpoint": "douyin_web.fetch_one_video",
  "path": "/api/v1/douyin/web/fetch_one_video",
  "data": { "aweme_detail": { "aweme_id": "7372484719365098803", "desc": "...", "statistics": { "digg_count": 12345 } } },
  "code": 200,
  "router": "/api/v1/douyin/web/fetch_one_video",
  "cost_usd": 0.001
}
```

`data` is the platform payload exactly as TikHub returns it - the shape
differs per endpoint and per platform. `code` / `router` are TikHub's own
envelope fields. `cost_usd` is what this call was billed.

`list_endpoints`:

```json
{
  "operation": "list_endpoints",
  "platform": "twitter",
  "count": 13,
  "total": 13,
  "endpoints": [
    {
      "endpoint": "twitter_web.fetch_search_timeline",
      "resource": "twitter_web",
      "method": "fetch_search_timeline",
      "http_method": "GET",
      "path": "/api/v1/twitter/web/fetch_search_timeline",
      "summary": "Search",
      "params": [
        { "name": "keyword", "type": "str", "required": true },
        { "name": "search_type", "type": "str | None", "required": false },
        { "name": "cursor", "type": "str | None", "required": false }
      ]
    }
  ]
}
```

`count` is how many endpoints came back after `search` + `limit`; `total`
is how many the platform has. With `platform: "all"` and no `search` the
listing is capped, so always narrow by platform or search term.

On failure the tool raises an error carrying TikHub's own message -
surface it verbatim (see "Errors" below).

## The discover-then-call loop

Never guess an endpoint id or its parameter names. Endpoints are
introspected from the installed SDK at runtime, so `list_endpoints` is
always exact, free, and returns the `required` flag for every parameter.

1. Narrow by platform and a search term:

```json
{ "operation": "list_endpoints", "platform": "douyin", "search": "comments" }
```

2. Read the `params` list of the endpoint you picked, then call it with
   exactly those keyword names:

```json
{ "operation": "call", "endpoint": "douyin_web.fetch_video_comments", "params": { "aweme_id": "7372484719365098803", "count": 20 } }
```

3. Paginate by feeding the cursor that came back in `data` into the next
   call (see "Pagination").

The `endpoint` field also accepts the REST path
(`/api/v1/douyin/web/fetch_video_comments`) or the slash spelling
(`douyin_web/fetch_video_comments`); all three resolve to the same SDK
method. An unknown id fails before any network call and the error lists
the closest matches.

Unknown keyword names are rejected before the request is sent, and the
error lists the accepted parameters - fix the names and retry, do not
retry the same call.

### POST batch endpoints

A few endpoints take a JSON body instead of query parameters (the SDK
signature shows a single `body` argument). Pass it as the `body` key
inside `params`:

```json
{ "operation": "call", "endpoint": "douyin_web.fetch_multi_video", "params": { "body": ["7372484719365098803", "7372484719365098804"] } }
```

## Share URLs: prefer fetch_url

For any TikTok or Douyin share link (including short links on
v.douyin.com and vm.tiktok.com), use `fetch_url` first. It resolves the
link and returns the full video payload in one billed request without you
having to extract an `aweme_id`:

```json
{ "operation": "fetch_url", "url": "https://www.tiktok.com/@scout2015/video/7372484719365098803" }
{ "operation": "fetch_url", "url": "https://v.douyin.com/iRNBho6u/", "minimal": true }
```

`minimal: true` trims the payload to the fields most tasks need (id,
description, author, stats, media URLs). For other platforms use the
platform's own URL-accepting endpoint (`instagram_v3.get_post_info` takes a
`url`, `kuaishou_web.fetch_one_video_by_url` takes a `url`,
`xiaohongshu_web.get_note_info_v7` takes `share_text`).

## Per-platform cheat sheet

Ids below are verified against the installed SDK. Parameter names are the
SDK keyword names; `list_endpoints` remains the authority for the full
signature.

### TikTok

Two resource families: `tiktok_web` (web-client fields, camelCase params
such as `secUid` / `uniqueId` / `itemId`) and `tiktok_app_v3` (app-client
fields, snake_case params such as `sec_user_id` / `unique_id` /
`aweme_id`). Both return TikTok data; the app family tends to carry richer
statistics, the web family is lighter.

| Endpoint | Required params | Notes |
|---|---|---|
| `tiktok_web.fetch_user_profile` | `uniqueId` or `secUid` | Profile by @handle (`uniqueId`) or sec id |
| `tiktok_web.fetch_user_post` | `secUid` | Paginate with `cursor` (int); `count` |
| `tiktok_web.fetch_post_detail` | `itemId` | Single video (web fields) |
| `tiktok_web.fetch_search_video` | `keyword` | Paginate with `offset` + `search_id` from the previous page |
| `tiktok_web.fetch_post_comment` | `aweme_id` | Paginate with `cursor`; `count` |
| `tiktok_app_v3.fetch_one_video` | `aweme_id` | Single video (app fields) |
| `tiktok_app_v3.fetch_one_video_by_share_url` | `share_url` | Video from a share link |
| `tiktok_app_v3.fetch_user_post_videos` | `sec_user_id` or `unique_id` | Paginate with `max_cursor`; `count` |
| `tiktok_app_v3.fetch_video_search_result` | `keyword` | `offset`, `count`, `sort_type`, `publish_time`, `region` |
| `tiktok_app_v3.handler_user_profile` | one of `user_id` / `sec_user_id` / `unique_id` | Profile (app fields) |
| `tiktok_app_v3.fetch_hashtag_video_list` | `ch_id` | Videos under a hashtag; get `ch_id` from `tiktok_app_v3.fetch_hashtag_search_result` |

### Douyin

`douyin_web` is the primary family; `douyin_app_v3` mirrors it with app
fields; `douyin_search` holds the current search endpoints (POST, but
still plain keyword params).

| Endpoint | Required params | Notes |
|---|---|---|
| `douyin_web.fetch_one_video` | `aweme_id` | Single video; `need_anchor_info` optional |
| `douyin_web.fetch_one_video_by_share_url` | `share_url` | Video from a share link (or use `fetch_url`) |
| `douyin_web.handler_user_profile` | `sec_user_id` | Profile; `douyin_web.handler_user_profile_v2` takes `unique_id` (the Douyin handle) |
| `douyin_web.fetch_user_post_videos` | `sec_user_id` | Paginate with `max_cursor` (string); `count` |
| `douyin_web.fetch_video_comments` | `aweme_id` | Paginate with `cursor`; `count` |
| `douyin_web.fetch_hot_search_result` | - | Hot search board |
| `douyin_search.fetch_video_search_v2` | `keyword` | Paginate with `cursor` + `search_id`; `sort_type`, `publish_time`, `filter_duration` |
| `douyin_app_v3.fetch_one_video_v3` | `aweme_id` | Video without copyright restrictions on media URLs |

### Instagram

Three generations exist: `instagram_v1`, `instagram_v2`, `instagram_v3`.
Prefer `instagram_v3` (newest; most endpoints accept either `user_id` or
`username`). `instagram_v2` remains useful for hashtag / location / music
feeds and paginates with `pagination_token`.

| Endpoint | Required params | Notes |
|---|---|---|
| `instagram_v3.get_user_profile` | `user_id` or `username` | Profile |
| `instagram_v3.get_user_posts` | `username` | Paginate with `after` (cursor) and `first` / `count` |
| `instagram_v3.get_user_reels` | `user_id` or `username` | Paginate with `after`; `page_size` |
| `instagram_v3.get_post_info` | `media_id` or `url` | Post from a URL or media id |
| `instagram_v3.get_post_comments` | `code` (the shortcode from the post URL) | Paginate with `min_id`; `sort_order` |
| `instagram_v3.general_search` | `query` | Paginate with `next_max_id` + `rank_token` |
| `instagram_v3.get_user_followers` | `user_id` or `username` | Paginate with `max_id`; `count` |
| `instagram_v2.fetch_hashtag_posts` | `keyword` | Paginate with `pagination_token`; `feed_type` |

### YouTube

`youtube_web` is the primary family; `youtube_web_v2` adds captions,
stream URLs, community posts and URL-accepting variants.

| Endpoint | Required params | Notes |
|---|---|---|
| `youtube_web.get_video_info_v3` | `video_id` | Video metadata; `language_code` |
| `youtube_web.get_channel_id` | `channel_name` | Resolve @handle to a channel id |
| `youtube_web.get_channel_info` | `channel_id` | Channel metadata |
| `youtube_web.get_channel_videos_v3` | `channel_id` | Paginate with `continuation_token` |
| `youtube_web.get_video_comments` | `video_id` | Paginate with `continuation_token`; `sort_by` |
| `youtube_web.get_general_search` | `search_query` | Filters: `upload_time`, `duration`, `content_type`, `sort_by`; paginate with `continuation_token` |
| `youtube_web_v2.get_video_captions` | `video_id` or `video_url` | Subtitle text; `language_code`, `format` |

### Twitter / X

| Endpoint | Required params | Notes |
|---|---|---|
| `twitter_web.fetch_tweet_detail` | `tweet_id` | Single tweet |
| `twitter_web.fetch_user_profile` | `screen_name` or `rest_id` | Profile |
| `twitter_web.fetch_user_post_tweet` | `screen_name` or `rest_id` | User timeline; paginate with `cursor` |
| `twitter_web.fetch_search_timeline` | `keyword` | `search_type` (Top / Latest / Media / People / Lists); paginate with `cursor` |
| `twitter_web.fetch_post_comments` | `tweet_id` | Replies; paginate with `cursor` |
| `twitter_web.fetch_trending` | - | `country` optional |

### Xiaohongshu (RedNote)

Families: `xiaohongshu_web` (note detail, search, user), `xiaohongshu_app_v2`
(comments, topic feeds, search variants), plus older `xiaohongshu_app`,
`xiaohongshu_web_v2`, `xiaohongshu_web_v3`. Most note endpoints accept
either a `note_id` or the raw `share_text` copied from the app.

| Endpoint | Required params | Notes |
|---|---|---|
| `xiaohongshu_web.get_note_info_v7` | `note_id` or `share_text` | Note detail (newest) |
| `xiaohongshu_web.get_note_id_and_xsec_token` | `share_text` | Resolve a share link to `note_id` + `xsec_token` |
| `xiaohongshu_web.search_notes_v3` | `keyword` | Paginate with `page`; `sort`, `noteType`, `noteTime` |
| `xiaohongshu_web.get_user_info` | `user_id` | Profile |
| `xiaohongshu_web.get_user_notes_v2` | `user_id` | Paginate with `lastCursor` |
| `xiaohongshu_app_v2.get_note_comments` | `note_id` or `share_text` | Paginate with `cursor`; `sort_strategy` |

### Other platforms

Every other family follows the same shape - run `list_endpoints` with the
platform to see them. Starting points: `bilibili_web.fetch_one_video`
(`bv_id`), `kuaishou_web.fetch_one_video_by_url` (`url`),
`weibo_web_v2.fetch_post_detail` (`id`), `reddit_app.fetch_post_details`
(`post_id`), `threads_web.fetch_post_detail` (`post_id`),
`linkedin_web_v2.get_user_profile` (`username`),
`zhihu_web.fetch_question_answers` (`question_id`).

### Hybrid parsing and account

| Endpoint | Required params | Notes |
|---|---|---|
| `hybrid_parsing.video_data` | `url` | What `fetch_url` calls; `minimal`, `base64_url` |
| `tikhub_user.get_user_info` | - | Balance, free credit, email (what `account` calls) |
| `tikhub_user.get_user_daily_usage` | - | Today's request count and spend (what `account` calls) |
| `tikhub_user.get_endpoint_info` | `endpoint` (a `/api/v1/...` path) | Price and description of one endpoint |
| `tikhub_user.calculate_price` | `endpoint` | Projected cost; `request_per_day` |

## Pagination

Cursor names vary by platform. Read the cursor from `data` and pass it
back under the parameter name the endpoint declares:

| Platform | Request param | Where the next cursor lives in `data` | Stop when |
|---|---|---|---|
| TikTok app / Douyin | `max_cursor` (user posts), `cursor` (comments, hashtags) | `max_cursor` / `cursor` | `has_more` is `false` or `0` |
| TikTok web | `cursor` (posts, comments), `offset` + `search_id` (search) | `cursor`, `search_id` | `hasMore` / `has_more` is false |
| Instagram v3 | `after` (posts, reels), `max_id` (followers), `min_id` (comments), `next_max_id` (search) | `end_cursor` under `page_info`, or `next_max_id` / `next_min_id` | `has_next_page` false or cursor absent |
| Instagram v2 | `pagination_token` | `pagination_token` | token absent |
| YouTube | `continuation_token` | `continuation_token` | token absent |
| Twitter | `cursor` | `cursor` (bottom cursor) | cursor repeats or no new entries |
| Xiaohongshu | `cursor` (app_v2), `lastCursor` (web), `page` (search) | `cursor` / `last_cursor` | `has_more` false |
| Weibo | `page` or `max_id` | `max_id` | empty page |
| Kuaishou | `pcursor` | `pcursor` | `pcursor` is `"no_more"` |

Fetch pages sequentially - each page is one billed request, and the same
endpoint path is limited to 10 requests per second.

## Cost and rate limits

- Roughly $0.001 per successful request (TikHub bills only 2xx responses;
  failed calls are free). `list_endpoints` never calls the API and costs
  nothing.
- 10 requests per second per endpoint path. Bursting past it returns 429;
  the SDK retries with backoff, and the tool reports `retry_after` when
  TikHub sends it.
- Before a large crawl (hundreds of pages), run `account` and tell the
  user the balance; `tikhub_user.calculate_price` gives a projection for
  one endpoint.
- Every `call` result carries `cost_usd`; costs are also recorded in
  OpenCompany's API usage panel under the `tikhub` service.

## Errors

The tool raises a plain error message; relay it to the user as-is and act
on the class of failure:

| Message contains | Meaning | What to do |
|---|---|---|
| `rejected the API key (401)` | Key missing, revoked or wrong | Tell the user to update it in Credentials -> TikHub; do not retry |
| `refused <endpoint> (403)` | Key lacks the endpoint's scope OR balance is exhausted | Run `account`; if balance is 0 tell the user to top up, otherwise the endpoint is outside the key's plan |
| `rate-limited <endpoint> (429)` | More than 10 req/s on one path | Wait `retry_after` seconds (or a few seconds), then retry once |
| `rejected the request to <endpoint> (400 or 422)` | Wrong or malformed argument values | The message carries TikHub's `detail`; fix the value and retry |
| `returned 404 for <endpoint>` | Route removed or id / resource no longer exists | Run `list_endpoints` and pick the current id |
| `upstream error while calling <endpoint>` (5xx / connection) | Platform-side failure after the SDK's retries | Try again later; try the `_v2` / `_v3` variant of the endpoint if one exists |
| `Unknown TikHub endpoint` | Id typo | Use the suggestions in the message or `list_endpoints` |
| `... rejected params` | Keyword name not in the SDK signature | Use the accepted names listed in the message |

A 200 whose body says `code: 4xx` is also raised as an error with
TikHub's message - the platform returned nothing useful for that id.

## Authentication

OpenCompany stores the TikHub API key encrypted; you never see it and
must never ask the user to paste it into the chat. If a call fails with
the 401 message, tell the user: open **Credentials -> Scrapers -> TikHub**,
paste the key from the TikHub user portal (tikhub.io -> API Keys) and
click Validate - the modal shows the account email and balance when the
key is accepted.

## Working inside a team

When this node is wired to a teammate rather than directly to the lead, the
lead never sees the `tikhub_action` tool itself. It sees one roster line per
teammate that lists the teammate's connected tools and skills, built from
this node's description and this skill's description, and it assigns work
through `task_manager` with a bounded mission. As the teammate holding
TikHub:

1. Treat the mission as the query: pick the platform from the URL or the
   wording, run `list_endpoints` if the endpoint id is not obvious, then
   `call` or `fetch_url`.
2. Return the extracted fields the mission asked for, not the raw TikHub
   payload. Include the endpoint id used, the count of items, and the total
   `cost_usd` so the lead can report spend.
3. If the key is missing or the balance is exhausted, say so in the result
   verbatim so the lead can escalate to the user; do not retry blindly.

## Best practices

1. **Prefer `fetch_url` for any share URL.** One request, no id
   extraction, works for TikTok and Douyin links including short links.
2. **Use `list_endpoints` before guessing.** It is free, exact for the
   installed SDK, and shows which params are required. Pick the highest
   `_vN` suffix when several variants exist unless the user needs a
   specific field set.
3. **Pass params by their SDK names**, as a JSON object, values typed as
   the signature says (`count` is an int, cursors are usually strings).
4. **Paginate deliberately.** Report how many pages you fetched and stop
   when `has_more` (or the platform's equivalent) turns false; do not loop
   without a page cap the user agreed to.
5. **Surface errors verbatim.** TikHub's `detail` strings are precise;
   do not paraphrase them or retry blindly on 401 / 403 / 404.
6. **Keep `data` intact when relaying to downstream nodes** - the raw
   platform payload is what other nodes and the user's exports expect.
7. **Respect the platforms' terms and the user's intent**: scrape public
   content only, do not collect personal data beyond the task, and do not
   hammer one endpoint past 10 req/s.
