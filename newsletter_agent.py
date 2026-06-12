import feedparser
import anthropic
import requests
import os
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── NEWSLETTER CONFIG ─────────────────────────────────────────────────────────

NEWSLETTER_NAME    = "Scope Creep"
NEWSLETTER_TAGLINE = "Top 5 product management reads, curated by AI — every Monday."
START_DATE         = datetime(2026, 4, 30)
LINKEDIN_URL       = "https://www.linkedin.com/in/mukherjee-koushik/"

def get_issue_number() -> int:
    weeks_since_start = ((datetime.now() - START_DATE).days // 7) + 1
    return max(1, weeks_since_start)

# ── SOURCES ───────────────────────────────────────────────────────────────────

REDDIT_FEEDS = [
    "https://www.reddit.com/r/ProductManagement/.rss",
    "https://www.reddit.com/r/ProductManagement_IN/.rss",
    "https://www.reddit.com/r/prodmgmt/.rss",
    "https://www.reddit.com/r/AIML/.rss",
    "https://www.reddit.com/r/interviews/.rss",
    "https://www.reddit.com/r/MadeMeSmile/.rss",
    "https://www.reddit.com/r/memes/.rss",
    "https://www.reddit.com/r/AIDankmemes/.rss",
]

GOOGLE_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=product+management&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=AI+product+management&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=product+manager+career&hl=en-IN&gl=IN&ceid=IN:en",
]

MEDIUM_URLS = [
    "https://pdmgr.medium.com/",
    "https://medium.com/@InnoThiga",
]

BLOG_URLS = [
    "https://www.theproductfolks.com/product-management-blog",
    "https://www.jefago.com/product-management/",
]

LINKEDIN_RSS_FEEDS = [
    "https://rsshub.app/linkedin/company/product-management-exercises",
    "https://rsshub.app/linkedin/company/product-management-learning-pml",
    "https://rsshub.app/linkedin/company/nyu-pmc",
    "https://rsshub.app/linkedin/in/sandeep-panda-226a5a26",
    "https://rsshub.app/linkedin/in/anirudh-sheldenkar-88b8b115",
]

PINTEREST_RSS_FEEDS = [
    "https://rsshub.app/pinterest/search/product%20management",
    "https://rsshub.app/pinterest/search/product%20design",
    "https://rsshub.app/pinterest/search/artificial%20intelligence",
    "https://rsshub.app/pinterest/search/AI%20PM",
]

YOUTUBE_HANDLES = [
    "@Atlassian",
    "@tryexponent",
    "@airtribe",
    "@LennysPodcast",
    "@ProductSchoolSanFrancisco",
    "@hellopm",
]

# ── POOL METADATA ─────────────────────────────────────────────────────────────
# Brand-accurate accent colors. Each card glows in its source's color.

POOL_META = {
    "Reddit":      {"color": "#ff4500", "emoji": "👾"},
    "Google News": {"color": "#4285f4", "emoji": "📰"},
    "Medium":      {"color": "#1a8917", "emoji": "✍️"},
    "Blog":        {"color": "#d97706", "emoji": "📝"},
    "LinkedIn":    {"color": "#0a66c2", "emoji": "💼"},
    "Pinterest":   {"color": "#e60023", "emoji": "📌"},
    "YouTube":     {"color": "#ff0033", "emoji": "▶️"},
    "Unknown":     {"color": "#7f8ca3", "emoji": "🔗"},
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
FEEDPARSER_AGENT = HEADERS["User-Agent"]


def extract_image(entry) -> str:
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image") or \
               m.get("url", "").endswith((".jpg", ".png", ".webp")):
                return m.get("url")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")
    if entry.get("summary"):
        soup = BeautifulSoup(entry["summary"], "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]
    return None


def fetch_rss(feeds: list[str], max_age_hours: int = None) -> list[dict]:
    articles = []
    cutoff = datetime.now() - timedelta(hours=max_age_hours) if max_age_hours else None
    for url in feeds:
        try:
            feed = feedparser.parse(url, agent=FEEDPARSER_AGENT)
            for entry in feed.entries[:15]:
                if cutoff:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                        if published < cutoff:
                            continue
                    except Exception:
                        pass
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "summary": entry.get("summary", "")[:500].strip(),
                    "source":  feed.feed.get("title", url),
                    "image":   extract_image(entry),
                    "pool":    None,
                })
        except Exception as e:
            print(f"  RSS error ({url}): {e}")
    return articles


def get_youtube_rss(handle: str) -> str:
    try:
        resp = requests.get(
            f"https://www.youtube.com/{handle}", headers=HEADERS, timeout=10
        )
        for pattern in [
            r'"channelId":"(UC[a-zA-Z0-9_-]+)"',
            r'"externalId":"(UC[a-zA-Z0-9_-]+)"',
        ]:
            match = re.search(pattern, resp.text)
            if match:
                return (
                    f"https://www.youtube.com/feeds/videos.xml"
                    f"?channel_id={match.group(1)}"
                )
    except Exception as e:
        print(f"  YouTube channel ID error ({handle}): {e}")
    return None


def fetch_youtube(handles: list[str]) -> list[dict]:
    articles = []
    for handle in handles:
        rss_url = get_youtube_rss(handle)
        if not rss_url:
            continue
        try:
            feed = feedparser.parse(rss_url, agent=FEEDPARSER_AGENT)
            for entry in feed.entries[:5]:
                thumbnail = None
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    thumbnail = entry.media_thumbnail[0].get("url")
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "summary": entry.get("summary", "")[:500].strip(),
                    "source":  f"YouTube: {feed.feed.get('title', handle)}",
                    "image":   thumbnail,
                    "pool":    "YouTube",
                })
            print(f"  {handle}: {len(feed.entries[:5])} videos")
        except Exception as e:
            print(f"  YouTube RSS error ({handle}): {e}")
    return articles


def fetch_medium(urls: list[str]) -> list[dict]:
    articles = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all("h2"):
                title = tag.get_text(strip=True)
                parent = tag.find_parent("a")
                link = parent["href"] if parent and parent.get("href") else url
                if not link.startswith("http"):
                    link = "https://medium.com" + link
                img = None
                container = tag.find_parent("div") or tag.find_parent("article")
                if container:
                    img_tag = container.find("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src")
                if title and len(title) > 15:
                    articles.append({
                        "title": title, "link": link, "summary": "",
                        "source": url, "image": img, "pool": "Medium",
                    })
        except Exception as e:
            print(f"  Medium error ({url}): {e}")
    return articles[:10]


def fetch_blogs(urls: list[str]) -> list[dict]:
    articles = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["h2", "h3"]):
                title = tag.get_text(strip=True)
                anchor = tag.find("a") or tag.find_parent("a")
                link = anchor["href"] if anchor and anchor.get("href") else url
                if not link.startswith("http"):
                    base = "/".join(url.split("/")[:3])
                    link = base + "/" + link.lstrip("/")
                img = None
                container = tag.find_parent("div") or tag.find_parent("article")
                if container:
                    img_tag = container.find("img")
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src")
                if title and len(title) > 15:
                    articles.append({
                        "title": title, "link": link, "summary": "",
                        "source": url, "image": img, "pool": "Blog",
                    })
        except Exception as e:
            print(f"  Blog error ({url}): {e}")
    return articles[:10]


# ── CLAUDE ────────────────────────────────────────────────────────────────────

def pick_and_summarise(
    client, articles: list[dict],
    source_label: str, already_picked: list[str],
) -> dict:
    candidates = [a for a in articles if a["link"] not in already_picked]
    if not candidates:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\nURL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(candidates[:20])
    ])

    prompt = f"""You are the editor of Scope Creep, a Product Management newsletter for PM professionals.

Source pool: {source_label}
Today: {datetime.now().strftime('%B %d, %Y')}

Pick the SINGLE most valuable article for a PM audience.
Prioritise: actionable insight, AI in product, career growth.
Avoid: memes, low-effort posts, generic news.

{numbered}

Write a newsletter summary of 4-5 sentences that explains what the article is about,
highlights 2-3 key takeaways a PM would care about, and ends with why this matters now.
Do NOT write a LinkedIn post. Write a newsletter summary paragraph only.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

SUMMARY:
[4-5 sentence newsletter summary paragraph]"""

    message = None
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 2:
                print(f"  Anthropic overloaded, retrying in 30s... (attempt {attempt+1})")
                time.sleep(30)
            else:
                raise

    text = message.content[0].text
    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            picked_index = idx

    return {"article": candidates[picked_index], "response": text}


def curate_five(all_pools: dict) -> list[dict]:
    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = []
    picked  = []

    pools_in_order = [
        ("REDDIT",                         all_pools["reddit"]),
        ("GOOGLE NEWS",                    all_pools["google"]),
        ("YOUTUBE / LINKEDIN / PINTEREST", all_pools["new"]),
        ("MEDIUM / BLOGS",                 all_pools["other"]),
        ("ALL SOURCES — wildcard",         all_pools["all"]),
    ]

    for label, pool in pools_in_order:
        if len(results) >= 5:
            break
        print(f"  Picking from {label}...")
        result = pick_and_summarise(client, pool, label, picked)
        if result:
            results.append(result)
            picked.append(result["article"]["link"])

    return results


# ── HTML NEWSLETTER ───────────────────────────────────────────────────────────
#
# Design system — "Aurora Editorial"
#   Void      #0d0d22  email body background
#   Panel     #15153a  hero / footer / index surfaces
#   Card      #181840  article card surface
#   Coral     #e94560  primary accent
#   Violet    #533483  secondary accent
#   Sky       #a8d8ea  tagline / soft text
#   Slate     #8e96c4  muted text
#   Per-card accents come from POOL_META (brand colors of each source).
#
# Signature element: the "aurora seam" — a segmented coral→violet→navy
# strip that opens the issue and recurs as a divider. It encodes the idea
# of many sources blending into one curated stream.
#
# Type: Arial Black masthead, Trebuchet MS headings/labels, Georgia body
# (all email-safe; Georgia gives the summaries an editorial, legible feel).

AURORA = ["#e94560", "#ef4e74", "#a23e88", "#533483", "#2c4a78", "#0f3460"]

SECTION_LABELS = [
    "Top Pick",
    "In the News",
    "Watch &amp; Learn",
    "Deep Read",
    "Wildcard",
]
SECTION_EMOJI = ["🔥", "📡", "🎬", "📖", "💡"]


def aurora_seam(height: int = 5, radius: str = "") -> str:
    """Segmented gradient strip — the issue's signature element."""
    cells = "".join(
        f'<td width="{100 // len(AURORA)}%" bgcolor="{c}" '
        f'style="background:{c};height:{height}px;font-size:1px;'
        f'line-height:1px;">&nbsp;</td>'
        for c in AURORA
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="{radius}"><tr>{cells}</tr></table>'
    )


def build_newsletter_html(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    issue    = get_issue_number()

    # ── Hidden preheader (inbox preview text) ────────────────────────────
    first_title = results[0]["article"]["title"] if results else ""
    preheader = (
        f"This week: {first_title} + {max(0, len(results) - 1)} more "
        f"hand-picked PM reads."
    )

    # ── "In this issue" index ────────────────────────────────────────────
    index_rows = []
    for i, result in enumerate(results):
        article = result["article"]
        pool    = article.get("pool", "Unknown")
        meta    = POOL_META.get(pool, POOL_META["Unknown"])
        label   = SECTION_LABELS[i] if i < len(SECTION_LABELS) else f"#{i+1}"
        index_rows.append(f"""
        <tr>
          <td width="36" valign="top" style="padding:0 0 14px 0;">
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         display:inline-block;width:26px;height:26px;
                         line-height:26px;text-align:center;
                         background:{meta['color']};color:#ffffff;
                         font-size:13px;font-weight:bold;
                         border-radius:13px;">{i+1}</span>
          </td>
          <td valign="top" style="padding:2px 0 14px 0;">
            <a href="{article['link']}" target="_blank"
               style="font-family:'Trebuchet MS',Arial,sans-serif;
                      color:#ffffff;font-size:15px;font-weight:bold;
                      line-height:1.45;text-decoration:none;">
              {article['title']}</a>
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         color:{meta['color']};font-size:12px;
                         font-weight:bold;">
              &nbsp;&middot;&nbsp;{label}</span>
          </td>
        </tr>""")
    index_html = "\n".join(index_rows)

    # ── Article cards ────────────────────────────────────────────────────
    cards = []
    for i, result in enumerate(results):
        article  = result["article"]
        response = result["response"]
        pool     = article.get("pool", "Unknown")
        meta     = POOL_META.get(pool, POOL_META["Unknown"])
        color    = meta["color"]
        emoji    = meta["emoji"]
        label    = SECTION_LABELS[i] if i < len(SECTION_LABELS) else f"#{i+1}"
        s_emoji  = SECTION_EMOJI[i] if i < len(SECTION_EMOJI) else "•"

        summary_match = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", response)
        summary       = summary_match.group(1).strip() if summary_match else ""
        summary_html  = summary.replace("\n", "<br>")

        # Prettify URL-style sources (e.g. Medium feeds) into clean labels
        source_label = article["source"]
        if source_label.startswith("http"):
            source_label = re.sub(r"^https?://(www\.)?", "", source_label).rstrip("/")

        img_html = ""
        if article.get("image"):
            img_html = f"""
        <tr>
          <td style="line-height:0;font-size:0;">
            <a href="{article['link']}" target="_blank" style="display:block;">
              <img src="{article['image']}" width="680"
                   style="display:block;width:100%;height:300px;
                          object-fit:cover;border:0;" alt="">
            </a>
          </td>
        </tr>"""

        cards.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#181840"
       style="margin-bottom:32px;border-radius:18px;overflow:hidden;
              background:#181840;border:1px solid {color};">
  {img_html}
  <tr>
    <td bgcolor="{color}" style="background:{color};padding:14px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:'Trebuchet MS',Arial,sans-serif;
                     color:#ffffff;font-size:15px;font-weight:bold;
                     letter-spacing:1px;text-transform:uppercase;">
            {s_emoji} &nbsp;{i+1} / {len(results)} &mdash; {label}
          </td>
          <td align="right">
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         background:#0d0d22;color:#ffffff;
                         font-size:11px;font-weight:bold;
                         padding:4px 12px;border-radius:20px;">
              {emoji} {pool}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="padding:30px 30px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding-bottom:12px;">
            <h2 style="font-family:'Trebuchet MS',Arial,sans-serif;
                       margin:0;font-size:24px;line-height:1.3;
                       font-weight:bold;color:#ffffff;">
              <a href="{article['link']}" target="_blank"
                 style="color:#ffffff;text-decoration:none;">
                {article['title']}</a>
            </h2>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:20px;">
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         color:{color};font-size:12px;font-weight:bold;
                         letter-spacing:0.8px;text-transform:uppercase;">
              {source_label[:55]}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:26px;border-left:4px solid {color};
                     padding-left:18px;">
            <p style="font-family:Georgia,'Times New Roman',serif;
                      margin:0;font-size:16px;line-height:1.85;
                      color:#cdd3f0;">
              {summary_html}
            </p>
          </td>
        </tr>
        <tr>
          <td bgcolor="{color}" style="background:{color};
                     border-radius:10px;text-align:center;">
            <a href="{article['link']}" target="_blank"
               style="font-family:'Trebuchet MS',Arial,sans-serif;
                      display:block;color:#ffffff !important;
                      font-size:15px;font-weight:bold;
                      padding:15px 24px;text-decoration:none;
                      border-radius:10px;mso-padding-alt:0;">
              {('Watch the video' if pool == 'YouTube' else 'Read the full piece')} &rarr;
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>""")

    cards_html = "\n".join(cards)

    pills = "".join([
        f'<span style="font-family:\'Trebuchet MS\',Arial,sans-serif;'
        f'display:inline-block;'
        f'background:{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]};'
        f'color:#ffffff;font-size:12px;font-weight:bold;'
        f'padding:5px 14px;border-radius:20px;margin:3px 4px;">'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["emoji"]} '
        f'{r["article"].get("pool","Unknown")}</span>'
        for r in results
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<title>{NEWSLETTER_NAME} — Issue #{issue}</title>
</head>
<body style="margin:0;padding:0;background:#0d0d22;" bgcolor="#0d0d22">

<!-- Preheader: shows in inbox preview, invisible in the email body -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;
            font-size:1px;line-height:1px;color:#0d0d22;">
  {preheader}
</div>

<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#0d0d22"
       style="background:#0d0d22;">
  <tr>
    <td align="center" style="padding:28px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:680px;">

        <!-- ══ HERO ══ -->
        <tr>
          <td style="border-radius:22px;overflow:hidden;">
            {aurora_seam(height=6)}
            <table width="100%" cellpadding="0" cellspacing="0"
                   bgcolor="#15153a" style="background:#15153a;">
              <tr>
                <td style="padding:44px 36px 40px;text-align:center;">
                  <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                               display:inline-block;
                               border:1px solid #e94560;color:#e94560;
                               font-size:12px;font-weight:bold;
                               letter-spacing:3px;text-transform:uppercase;
                               padding:6px 18px;border-radius:20px;
                               margin-bottom:20px;">
                    Issue #{issue} &nbsp;&middot;&nbsp; {date_str}
                  </span>
                  <h1 style="font-family:'Arial Black','Trebuchet MS',Arial,sans-serif;
                             margin:0 0 14px 0;color:#ffffff;
                             font-size:52px;font-weight:900;
                             letter-spacing:-1px;line-height:1.05;">
                    {NEWSLETTER_NAME}
                  </h1>
                  <p style="font-family:Georgia,'Times New Roman',serif;
                            font-style:italic;
                            margin:0 0 24px 0;color:#a8d8ea;
                            font-size:16px;line-height:1.6;">
                    {NEWSLETTER_TAGLINE}
                  </p>
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                            margin:0;color:#8e96c4;font-size:12px;
                            letter-spacing:0.5px;">
                    Reddit &middot; Google News &middot; YouTube &middot;
                    LinkedIn &middot; Pinterest &middot; Medium &middot;
                    PM Blogs &mdash; one inbox.
                  </p>
                </td>
              </tr>
            </table>
            {aurora_seam(height=6)}
          </td>
        </tr>

        <tr><td style="height:26px;font-size:1px;">&nbsp;</td></tr>

        <!-- ══ IN THIS ISSUE ══ -->
        <tr>
          <td bgcolor="#15153a"
              style="background:#15153a;border-radius:18px;
                     padding:26px 28px 14px;border:1px solid #2a2a5e;">
            <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                      margin:0 0 18px 0;color:#e94560;
                      font-size:12px;font-weight:bold;
                      text-transform:uppercase;letter-spacing:2.5px;">
              In this issue
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              {index_html}
            </table>
            <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                      margin:6px 0 12px 0;font-size:11px;
                      color:#8e96c4;letter-spacing:1px;
                      text-transform:uppercase;">
              This week's sources
            </p>
            <p style="margin:0 0 12px 0;">{pills}</p>
          </td>
        </tr>

        <tr><td style="height:26px;font-size:1px;">&nbsp;</td></tr>

        <!-- ══ INTRO NOTE ══ -->
        <tr>
          <td bgcolor="#181840"
              style="background:#181840;border-radius:18px;
                     padding:26px 30px;border-left:5px solid #e94560;">
            <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                      margin:0 0 10px 0;font-size:17px;
                      line-height:1.6;color:#ffffff;font-weight:bold;">
              Hey there! Welcome to this week's edition of {NEWSLETTER_NAME}.
            </p>
            <p style="font-family:Georgia,'Times New Roman',serif;
                      margin:0;font-size:15px;line-height:1.8;
                      color:#cdd3f0;">
              Five reads, one agent, zero fluff. Each pick below was
              pulled from a different corner of the PM internet and
              summarised so you know in 30 seconds whether it deserves
              your next coffee break.
            </p>
          </td>
        </tr>

        <tr><td style="height:32px;font-size:1px;">&nbsp;</td></tr>

        <!-- ══ ARTICLE CARDS ══ -->
        <tr>
          <td>
            {cards_html}
          </td>
        </tr>

        <!-- ══ FOOTER ══ -->
        <tr>
          <td style="border-radius:18px;overflow:hidden;">
            {aurora_seam(height=4)}
            <table width="100%" cellpadding="0" cellspacing="0"
                   bgcolor="#15153a" style="background:#15153a;">
              <tr>
                <td style="padding:30px 28px;text-align:center;">
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                            margin:0 0 12px 0;color:#ffffff;
                            font-size:14px;font-weight:bold;">
                    Enjoyed this issue? Forward it to a PM friend.
                  </p>
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                            margin:0 0 16px 0;color:#a8d8ea;
                            font-size:13px;">
                    Curated by Koushik &mdash;
                    <a href="{LINKEDIN_URL}" target="_blank"
                       style="color:#e94560;font-weight:bold;
                              text-decoration:none;">
                      say hi on LinkedIn &rarr;</a>
                  </p>
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                            margin:0;color:#8e96c4;font-size:11px;
                            line-height:1.8;">
                    You're receiving this because you subscribed to
                    {NEWSLETTER_NAME}. &nbsp;&middot;&nbsp;
                    Powered by Claude Haiku &amp; Buttondown
                    &nbsp;&middot;&nbsp; Built on GitHub Actions
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr><td style="height:24px;font-size:1px;">&nbsp;</td></tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""


# ── BUTTONDOWN ────────────────────────────────────────────────────────────────

def send_to_buttondown(html: str, results: list[dict]):
    api_key  = os.environ["BUTTONDOWN_API_KEY"]
    issue    = get_issue_number()
    date_str = datetime.now().strftime("%B %d, %Y")

    subject = (
        f"{NEWSLETTER_NAME} #{issue} — "
        f"Top {len(results)} PM Reads | {date_str}"
    )

    resp = requests.post(
        "https://api.buttondown.email/v1/emails",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "subject": subject,
            "body":    html,
            "status":  "draft",
        },
        timeout=30,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"  Draft created in Buttondown!")
        print(f"  Email ID : {data.get('id')}")
        print(f"  Subject  : {subject}")
        print(f"  Go to buttondown.com/emails to review and send.")
    else:
        print(f"  Buttondown API error {resp.status_code}: {resp.text}")
        raise SystemExit(1)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/3 — Fetching all sources...")

    reddit = fetch_rss(REDDIT_FEEDS)
    for a in reddit:
        a["pool"] = "Reddit"
    print(f"  Reddit: {len(reddit)}")

    google = fetch_rss(GOOGLE_NEWS_FEEDS, max_age_hours=168)
    for a in google:
        a["pool"] = "Google News"
    print(f"  Google News: {len(google)}")

    linkedin = fetch_rss(LINKEDIN_RSS_FEEDS)
    for a in linkedin:
        a["pool"] = "LinkedIn"
    print(f"  LinkedIn RSS: {len(linkedin)}")

    pinterest = fetch_rss(PINTEREST_RSS_FEEDS)
    for a in pinterest:
        a["pool"] = "Pinterest"
    print(f"  Pinterest RSS: {len(pinterest)}")

    youtube = fetch_youtube(YOUTUBE_HANDLES)
    print(f"  YouTube: {len(youtube)}")

    medium = fetch_medium(MEDIUM_URLS)
    print(f"  Medium: {len(medium)}")

    blogs = fetch_blogs(BLOG_URLS)
    print(f"  Blogs: {len(blogs)}")

    all_articles = (
        reddit + google + linkedin + pinterest + youtube + medium + blogs
    )
    print(f"  Total: {len(all_articles)} articles collected")

    print("\nStep 2/3 — Claude Haiku: curating top 5...")
    results = curate_five({
        "reddit": reddit,
        "google": google,
        "new":    linkedin + pinterest + youtube,
        "other":  medium + blogs,
        "all":    all_articles,
    })
    print(f"  {len(results)} articles selected")

    print("\nStep 3/3 — Building newsletter and sending to Buttondown...")
    html = build_newsletter_html(results)
    send_to_buttondown(html, results)
    print("\nDone!")


if __name__ == "__main__":
    main()
