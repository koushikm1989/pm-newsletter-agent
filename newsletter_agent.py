import feedparser
import anthropic
import requests
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── NEWSLETTER CONFIG ─────────────────────────────────────────────────────────

NEWSLETTER_NAME   = "PM Pulse Weekly"
NEWSLETTER_TAGLINE = "Top 5 product management reads, curated by AI — every Monday."
ISSUE_NUMBER      = None  # Set to an integer e.g. 1 to override auto-numbering

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

POOL_META = {
    "Reddit":      {"color": "#ff4500", "emoji": "👾", "light": "#fff3f0"},
    "Google News": {"color": "#4285f4", "emoji": "📰", "light": "#f0f5ff"},
    "Medium":      {"color": "#292929", "emoji": "✍️", "light": "#f7f7f7"},
    "Blog":        {"color": "#1a73e8", "emoji": "📝", "light": "#f0f5ff"},
    "LinkedIn":    {"color": "#0077b5", "emoji": "💼", "light": "#eef7fc"},
    "Pinterest":   {"color": "#e60023", "emoji": "📌", "light": "#fff0f1"},
    "YouTube":     {"color": "#ff0000", "emoji": "▶️", "light": "#fff2f2"},
    "Unknown":     {"color": "#888888", "emoji": "🔗", "light": "#f5f5f5"},
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
                        "title": title, "link": link,
                        "summary": "", "source": url,
                        "image": img, "pool": "Medium",
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
                        "title": title, "link": link,
                        "summary": "", "source": url,
                        "image": img, "pool": "Blog",
                    })
        except Exception as e:
            print(f"  Blog error ({url}): {e}")
    return articles[:10]


# ── CLAUDE ────────────────────────────────────────────────────────────────────

def pick_and_summarise(
    client,
    articles: list[dict],
    source_label: str,
    already_picked: list[str],
) -> dict:
    candidates = [a for a in articles if a["link"] not in already_picked]
    if not candidates:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\n"
        f"URL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(candidates[:20])
    ])

    prompt = f"""You are the editor of PM Pulse Weekly, a Product Management newsletter for Indian PM professionals.

Source pool: {source_label}
Today: {datetime.now().strftime('%B %d, %Y')}

From the articles below, pick the SINGLE most valuable one for a PM audience.
Prioritise: actionable insight, AI in product, career growth, India tech scene. 
Avoid: memes, low-effort posts, generic news.

{numbered}

Write a newsletter summary of 4-5 sentences that:
- Explains what the article is about
- Highlights 2-3 key takeaways a PM would care about
- Ends with why this matters right now
Do NOT write a LinkedIn post. Write a newsletter summary paragraph.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

SUMMARY:
[4-5 sentence newsletter summary paragraph]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            picked_index = idx

    return {"article": candidates[picked_index], "response": text}


def curate_five(all_pools: dict) -> list[dict]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results   = []
    picked    = []

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

def build_newsletter_html(results: list[dict]) -> str:
    date_str  = datetime.now().strftime("%B %d, %Y")
    week_num  = datetime.now().isocalendar()[1]
    issue     = ISSUE_NUMBER or week_num

    # ── Article cards ────────────────────────────────────────────────────────
    cards = []
    for i, result in enumerate(results):
        article  = result["article"]
        response = result["response"]
        pool     = article.get("pool", "Unknown")
        meta     = POOL_META.get(pool, POOL_META["Unknown"])
        color    = meta["color"]
        light    = meta["light"]
        emoji    = meta["emoji"]

        summary_match = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", response)
        summary = summary_match.group(1).strip() if summary_match else ""
        summary_html = summary.replace("\n", "<br>")

        img_html = ""
        if article.get("image"):
            img_html = f"""
            <div style="margin:0 0 20px;border-radius:10px;overflow:hidden;">
              <img src="{article['image']}"
                   style="width:100%;max-height:240px;object-fit:cover;display:block;"
                   alt="">
            </div>"""

        divider = '<div style="border-top:1px solid #ebebeb;margin:32px 0;"></div>' \
                  if i < len(results) - 1 else ""

        cards.append(f"""
        <!-- Article {i+1} -->
        <div style="margin-bottom:8px;">

          <!-- Number + source row -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
            <tr>
              <td>
                <span style="font-size:11px;font-weight:700;color:#aaa;
                             text-transform:uppercase;letter-spacing:1px;">
                  {i+1} of {len(results)}
                </span>
              </td>
              <td align="right">
                <span style="background:{color};color:#fff;font-size:11px;
                             font-weight:700;padding:3px 10px;border-radius:20px;">
                  {emoji} {pool}
                </span>
              </td>
            </tr>
          </table>

          {img_html}

          <!-- Title -->
          <h2 style="margin:0 0 6px;font-size:20px;line-height:1.3;font-weight:700;">
            <a href="{article['link']}"
               style="color:#111111;text-decoration:none;"
               target="_blank">{article['title']}</a>
          </h2>

          <!-- Source -->
          <p style="margin:0 0 14px;font-size:12px;color:#999;">
            {article['source']}
          </p>

          <!-- Summary -->
          <p style="margin:0 0 18px;font-size:15px;line-height:1.75;color:#444;">
            {summary_html}
          </p>

          <!-- CTA button -->
          <a href="{article['link']}"
             style="display:inline-block;background:{color};color:#ffffff;
                    font-size:13px;font-weight:600;padding:10px 22px;
                    border-radius:8px;text-decoration:none;"
             target="_blank">
            Read Full Article →
          </a>

        </div>
        {divider}""")

    cards_html = "\n".join(cards)

    # ── Source pills ─────────────────────────────────────────────────────────
    pills = "".join([
        f'<span style="display:inline-block;background:'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]};'
        f'color:#fff;font-size:11px;font-weight:700;padding:3px 10px;'
        f'border-radius:20px;margin:2px 3px;">'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["emoji"]} '
        f'{r["article"].get("pool","Unknown")}</span>'
        for r in results
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{NEWSLETTER_NAME} — Issue #{issue}</title>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
             Roboto,Helvetica,Arial,sans-serif;">

<div style="max-width:620px;margin:0 auto;padding:32px 16px;">

  <!-- ── HEADER ── -->
  <div style="background:linear-gradient(135deg,#0f2a4a 0%,#1a5276 60%,#0077b5 100%);
              border-radius:16px;padding:40px 36px;margin-bottom:24px;
              text-align:center;">
    <p style="margin:0 0 6px;color:#7ec8e3;font-size:12px;font-weight:700;
               text-transform:uppercase;letter-spacing:2px;">
      Issue #{issue} &nbsp;·&nbsp; {date_str}
    </p>
    <h1 style="margin:0 0 10px;color:#ffffff;font-size:30px;
               font-weight:800;letter-spacing:-0.5px;">
      {NEWSLETTER_NAME}
    </h1>
    <p style="margin:0;color:#a8d8ea;font-size:14px;line-height:1.6;">
      {NEWSLETTER_TAGLINE}
    </p>
  </div>

  <!-- ── INTRO STRIP ── -->
  <div style="background:#ffffff;border-radius:12px;padding:20px 24px;
              margin-bottom:24px;border:1px solid #e5e7eb;">
    <p style="margin:0 0 10px;font-size:13px;font-weight:700;color:#888;
               text-transform:uppercase;letter-spacing:0.8px;">
      This week's sources
    </p>
    <div>{pills}</div>
  </div>

  <!-- ── MAIN CARD ── -->
  <div style="background:#ffffff;border-radius:16px;padding:36px 32px;
              border:1px solid #e5e7eb;
              box-shadow:0 4px 24px rgba(0,0,0,0.06);">

    {cards_html}

  </div>

  <!-- ── FOOTER ── -->
  <div style="text-align:center;padding:28px 0 8px;">
    <p style="color:#aaa;font-size:12px;margin:0 0 4px;">
      You're receiving this because you subscribed to {NEWSLETTER_NAME}.
    </p>
    <p style="color:#bbb;font-size:11px;margin:0;">
      Curated by AI &nbsp;·&nbsp; Powered by Claude Haiku &amp; Beehiiv
      &nbsp;·&nbsp; Built on GitHub Actions
    </p>
  </div>

</div>
</body>
</html>"""


# ── BEEHIIV ───────────────────────────────────────────────────────────────────

def send_to_beehiiv(html: str, results: list[dict]):
    api_key = os.environ["BEEHIIV_API_KEY"]
    pub_id  = os.environ["BEEHIIV_PUBLICATION_ID"]
    week    = datetime.now().isocalendar()[1]
    issue   = ISSUE_NUMBER or week
    date_str = datetime.now().strftime("%B %d, %Y")

    subject  = f"{NEWSLETTER_NAME} #{issue} — Top {len(results)} PM Reads | {date_str}"
    preview  = " · ".join([r["article"]["title"][:40] for r in results[:3]])

    payload = {
        "title":        f"{NEWSLETTER_NAME} #{issue} — {date_str}",
        "subject":      subject,
        "preview_text": preview,
        "content_tags": ["product-management", "AI", "weekly"],
        "status":       "draft",
        "free_content": html,
    }

    resp = requests.post(
        f"https://api.beehiiv.com/v2/publications/{pub_id}/posts",
        headers={
            "Authorization":  f"Bearer {api_key}",
            "Content-Type":   "application/json",
            "Accept":         "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        print(f"  Draft created in Beehiiv!")
        print(f"  Post ID : {data.get('id')}")
        print(f"  Subject : {subject}")
        print(f"  Status  : {data.get('status')}")
        print(f"  Review and send from your Beehiiv dashboard.")
    else:
        print(f"  Beehiiv API error {resp.status_code}: {resp.text}")
        raise SystemExit(1)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/3 — Fetching all sources...")

    reddit = fetch_rss(REDDIT_FEEDS)
    for a in reddit: a["pool"] = "Reddit"
    print(f"  Reddit: {len(reddit)}")

    google = fetch_rss(GOOGLE_NEWS_FEEDS, max_age_hours=168)
    for a in google: a["pool"] = "Google News"
    print(f"  Google News: {len(google)}")

    linkedin = fetch_rss(LINKEDIN_RSS_FEEDS)
    for a in linkedin: a["pool"] = "LinkedIn"
    print(f"  LinkedIn RSS: {len(linkedin)}")

    pinterest = fetch_rss(PINTEREST_RSS_FEEDS)
    for a in pinterest: a["pool"] = "Pinterest"
    print(f"  Pinterest RSS: {len(pinterest)}")

    youtube = fetch_youtube(YOUTUBE_HANDLES)
    print(f"  YouTube: {len(youtube)}")

    medium = fetch_medium(MEDIUM_URLS)
    print(f"  Medium: {len(medium)}")

    blogs = fetch_blogs(BLOG_URLS)
    print(f"  Blogs: {len(blogs)}")

    all_articles = reddit + google + linkedin + pinterest + youtube + medium + blogs
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

    print("\nStep 3/3 — Building newsletter and sending to Beehiiv...")
    html = build_newsletter_html(results)
    send_to_beehiiv(html, results)
    print("\nDone!")


if __name__ == "__main__":
    main()
