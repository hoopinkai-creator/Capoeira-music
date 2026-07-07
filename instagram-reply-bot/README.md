# Instagram Reply Bot

A small, standalone tool that reads comments on an Instagram reel/post and posts
replies — from a template or an optional AI model. It uses the **official
Instagram Graph API** (no scraping), defaults to a **dry run**, and keeps a
ledger so it never replies to the same comment twice.

Built to answer comments on
[this reel](https://www.instagram.com/reel/Dac_XkRBKzo/), but it works for any
reel/post owned by the account whose token you provide.

> This is its own self-contained project — it does not depend on anything else
> in the surrounding repository.

## What you need first

The Graph API only lets you manage comments on media you own, so:

1. An Instagram **Business or Creator** account (the one that posted the reel).
2. That account linked to a **Facebook Page**.
3. A **Meta app** (https://developers.facebook.com) with the Instagram Graph API
   product added.
4. A long-lived **access token** with these permissions:
   `instagram_basic`, `instagram_manage_comments`, `pages_read_engagement`.
5. Your numeric **IG user id** (the business account id).

Meta's guide: **Instagram API → Comment Moderation**
(https://developers.facebook.com/docs/instagram-api/guides/comment-moderation).

## Install

```bash
cd instagram-reply-bot
python -m pip install -e .          # core (template replies)
python -m pip install -e '.[ai]'    # + AI-composed replies (Anthropic)
python -m pip install -e '.[dev]'   # + pytest
```

## Configure

```bash
cp config.example.yaml config.yaml   # edit post_url / reply style
```

Secrets stay in the environment (never in the config file):

```bash
export INSTAGRAM_ACCESS_TOKEN="EAAG...your-long-lived-token"
export INSTAGRAM_USER_ID="17841400000000000"
# optional:
export INSTAGRAM_USERNAME="your_handle"     # so it skips your own comments
export ANTHROPIC_API_KEY="sk-ant-..."       # only if reply_mode: ai
```

## Use

```bash
ig-reply-bot check          # verify credentials + resolve the post
ig-reply-bot comments       # list the comments on the post
ig-reply-bot reply          # DRY RUN — shows what it would send (posts nothing)
ig-reply-bot reply --send   # actually post the replies
ig-reply-bot reply --send --limit 5
```

`reply` always skips comments already in the ledger (`instagram_replies.json`),
so you can run it on a schedule (cron, GitHub Actions, etc.) and it only answers
new comments.

## Reply styles

Set `reply_mode` in `config.yaml`:

- **`template`** (default) — fills `reply_template` with `{name}` and `{text}`,
  e.g. `"Axé! 🙏 Obrigado pelo comentário, @{name}!"`.
- **`ai`** — asks an Anthropic model for one short, warm reply in the
  commenter's language. Requires the `[ai]` extra and `ANTHROPIC_API_KEY`. If AI
  is unavailable or errors, it silently falls back to the template.

## How it works

```
config.yaml + env ─▶ resolve post_url → media id (find_media_id)
                     read comments      (list_comments)
                     skip already-replied / own comments
                     compose reply      (template | AI)
                     post reply         (reply_to_comment)   ← only with --send
                     record id          (instagram_replies.json)
```

## Develop / test

```bash
python -m pytest        # network is fully stubbed; no real API calls
```

The Graph client takes an injectable `opener`, and `run()` takes an injectable
`client`, so the whole flow is tested offline.

## Notes & limits

- The API returns **top-level** comments; replies are posted as replies to those
  comments.
- Instagram rate-limits comment writes — use `--limit` and space out runs if you
  have a large backlog.
- There's no public shortcode→media-id lookup, so the bot finds the media by
  paging your account's media and matching the permalink. If your post is far
  back in the feed, set `media_id` directly in `config.yaml` to skip the search.
- Respect Instagram's Platform Terms and only auto-reply on accounts you own.
