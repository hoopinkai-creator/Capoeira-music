# Instagram Reply Bot

A small, standalone tool that reads comments on your Instagram reels/posts and
posts replies — a **ManyChat-style** comment-automation bot. It uses the
**official Instagram Graph API** (no scraping), defaults to a **dry run**, and
keeps a ledger so it never replies to the same comment twice.

What it does (the ManyChat feature set, in code):

- Run on **one post, a list of posts, or every post on the account**.
- Match comments against **keyword rules** (first match wins).
- Post a **public reply**, and optionally send a **DM / private reply** — just
  like ManyChat's "comment → DM" flows.
- Fall back to a default template (or an AI-written reply) when no rule matches.
- Run **on a schedule** via the included GitHub Actions workflow.

Built to answer comments on
[this reel](https://www.instagram.com/reel/Dac_XkRBKzo/), but it works for any
reel/post owned by the account whose token you provide.

> This is its own self-contained project — it does not depend on anything else
> in the surrounding repository.

### Note on "replicating ManyChat"

ManyChat is a closed-source SaaS, so there's no source to copy. This replicates
its *behaviour* — keyword-triggered public replies + DMs across your posts —
using Instagram's official APIs. The DM feature uses Instagram **private
replies** (`instagram_manage_messages`); public replies use comment moderation
(`instagram_manage_comments`).

## What you need first

The Graph API only lets you manage comments on media you own, so:

1. An Instagram **Business or Creator** account (the one that posted the reel).
2. That account linked to a **Facebook Page**.
3. A **Meta app** (https://developers.facebook.com) with the Instagram Graph API
   product added.
4. A long-lived **access token** with these permissions:
   `instagram_basic`, `instagram_manage_comments`, `pages_read_engagement`,
   and `instagram_manage_messages` (only if you use rule **DMs**).
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

## Which posts it replies on

Pick one in `config.yaml`:

```yaml
post_url: "https://www.instagram.com/reel/Dac_XkRBKzo/"   # a single post
# posts: ["https://.../reel/AAA/", "https://.../p/BBB/"]  # several posts
# auto_discover: true                                      # every post on the account
# max_posts: 25                                            #   (cap for auto_discover)
# media_id: "17900000000000000"                            # a raw media id
```

`auto_discover: true` is the "reply everywhere" mode — it pages through your
account's media and processes each one.

## ManyChat-style keyword rules

Rules turn specific comments into specific replies (and optional DMs). The first
rule whose keyword appears in the comment wins:

```yaml
rules:
  - name: pricing
    keywords: ["price", "preço", "quanto custa"]
    reply: "Oi @{name}! Te mandei os valores no direct 🙌"   # public reply
    dm: "Class prices: R$120/month. Reply to sign up 🥋"     # private reply (DM)
    match: substring        # substring (default) | word | exact
only_rules: false           # true = stay silent unless a rule matches
send_dm: true               # send rule DMs (needs instagram_manage_messages)
```

`{name}` and `{text}` are filled from the comment. DMs use Instagram private
replies and must go out within 7 days of the comment.

## Default reply style (when no rule matches)

Set `reply_mode`:

- **`template`** (default) — fills `reply_template` with `{name}` and `{text}`.
- **`ai`** — asks an Anthropic model for one short, warm reply in the
  commenter's language. Requires the `[ai]` extra and `ANTHROPIC_API_KEY`. If AI
  is unavailable or errors, it silently falls back to the template.

## Run on a schedule (GitHub Actions)

A workflow is included at repo root:
[`.github/workflows/instagram-reply-bot.yml`](../.github/workflows/instagram-reply-bot.yml).
It runs `ig-reply-bot reply --send` every 30 minutes and caches the ledger
between runs. Add `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` (and
`ANTHROPIC_API_KEY` if using AI) as repository secrets. Trigger it manually from
the Actions tab (defaults to a dry run) to test first.

> GitHub only runs workflows from the **repo root** `.github/workflows/`, which
> is why the file lives there rather than inside this folder. If you extract
> this project into its own repository, move it to that repo's
> `.github/workflows/` and drop the `working-directory:` line.

## How it works

```
config.yaml + env ─▶ resolve targets   (post_url | posts | auto_discover)
                     for each post:
                       read comments    (list_comments)
                       skip already-replied / own comments
                       plan reply       (keyword rule → reply + DM, else default)
                       post reply       (reply_to_comment)      ← only with --send
                       send DM          (send_private_reply)    ← only with --send
                       record id        (instagram_replies.json)
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
