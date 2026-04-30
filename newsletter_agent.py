import feedparser
import anthropic
import requests
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── NEWSLETTER CONFIG ─────────────────────────────────────────────────────────

NEWSLETTER_NAME    = "Scope Creep"
NEWSLETTER_TAGLINE = "Top 5 product management reads, curated by AI — every Monday."
START_DATE         = datetime(2026, 4, 30)  # Issue #1 date — update this once

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

POOL_META = {
    "Reddit":      {"color": "#ff4500", "emoji": "👾", "bg": "#fff3f0", "border": "#ffb89a"},
    "Google News": {"color": "#1a73e8", "emoji": "📰", "bg": "#f0f5ff", "border": "#a8c4f8"},
    "Medium":      {"color": "#292929", "emoji": "✍️", "bg": "#f7f7f7", "border": "#cccccc"},
    "Blog":        {"color": "#0f5bbf", "emoji": "📝", "bg": "#eef4ff", "border": "#93bbf5"},
    "LinkedIn":    {"color": "#0077b5", "emoji": "💼", "bg": "#eef7fc", "border": "#7ec8e3"},
    "Pinterest":   {"color": "#ad081b", "emoji": "📌", "bg": "#fff0f1", "border": "#f5a0a8"},
    "YouTube":     {"color": "#cc0000", "emoji": "▶️", "bg": "#fff2f2", "border": "#ffaaaa"},
    "Unknown":     {"color": "#444444", "emoji": "🔗", "bg": "#f5f5f5", "border": "#cccccc"},
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

def build_newsletter_html(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    issue    = get_issue_number()

    section_labels = [
        "🔥 Top Pick",
        "📡 In the News",
        "🎬 Watch & Learn",
        "📖 Deep Read",
        "💡 Wildcard",
    ]

    cards = []
    for i, result in enumerate(results):
        article  = result["article"]
        response = result["response"]
        pool     = article.get("pool", "Unknown")
        meta     = POOL_META.get(pool, POOL_META["Unknown"])
        color    = meta["color"]
        bg       = meta["bg"]
        border   = meta["border"]
        emoji    = meta["emoji"]
        label    = section_labels[i] if i < len(section_labels) else f"#{i+1}"

        summary_match = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", response)
        summary       = summary_match.group(1).strip() if summary_match else ""
        summary_html  = summary.replace("\n", "<br>")

        img_html = ""
        if article.get("image"):
            img_html = f"""
            <tr>
              <td style="padding:0 0 20px 0;line-height:0;">
                <img src="{article['image']}"
                     width="100%"
                     style="display:block;width:100%;max-height:220px;
                            object-fit:cover;border-radius:8px;"
                     alt="">
              </td>
            </tr>"""

        cards.append(f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-bottom:24px;border-radius:16px;
              overflow:hidden;border:2px solid {border};">
  <tr>
    <td style="background:{color};padding:12px 20px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:Arial,sans-serif;color:#ffffff;
                     font-size:13px;font-weight:700;
                     letter-spacing:0.5px;">
            {label}
          </td>
          <td align="right">
            <span style="font-family:Arial,sans-serif;
                         background:rgba(255,255,255,0.22);
                         color:#ffffff;font-size:11px;
                         font-weight:700;padding:3px 10px;
                         border-radius:20px;">
              {emoji} {pool}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="background:{bg};padding:24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        {img_html}
        <tr>
          <td style="padding-bottom:10px;">
            <h2 style="font-family:Arial,sans-serif;margin:0;
                       font-size:18px;line-height:1.35;
                       font-weight:800;color:#111111;">
              <a href="{article['link']}"
                 style="color:#111111;text-decoration:none;"
                 target="_blank">{article['title']}</a>
            </h2>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:16px;">
            <span style="font-family:Arial,sans-serif;
                         display:inline-block;
                         background:{color};
                         color:#ffffff;
                         font-size:10px;font-weight:700;
                         padding:3px 10px;border-radius:4px;
                         letter-spacing:0.5px;
                         text-transform:uppercase;">
              {article['source'][:55]}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:20px;
                     border-left:4px solid {color};
                     padding-left:14px;">
            <p style="font-family:Arial,sans-serif;
                      margin:0;font-size:14px;
                      line-height:1.8;color:#333333;">
              {summary_html}
            </p>
          </td>
        </tr>
        <tr>
          <td>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:{color};
                           border-radius:8px;">
                  <a href="{article['link']}"
                     target="_blank"
                     style="font-family:Arial,sans-serif;
                            display:inline-block;
                            color:#ffffff !important;
                            font-size:13px;font-weight:700;
                            padding:12px 24px;
                            text-decoration:none;
                            border-radius:8px;
                            mso-padding-alt:0;">
                    Read Full Article &rarr;
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>""")

    cards_html = "\n".join(cards)

    pills = "".join([
        f'<span style="font-family:Arial,sans-serif;'
        f'display:inline-block;'
        f'background:{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]};'
        f'color:#ffffff;font-size:11px;font-weight:700;'
        f'padding:4px 12px;border-radius:20px;margin:3px 4px;">'
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
<body style="margin:0;padding:0;background:#1a1a2e;">

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#1a1a2e;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:620px;">

        <!-- ══ HEADER ══ -->
        <tr>
          <td style="border-radius:20px;overflow:hidden;
                     background:#0f3460;">

            <!-- Rainbow top bar -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="33%" style="background:#e94560;
                    height:5px;font-size:1px;line-height:1px;">&nbsp;</td>
                <td width="34%" style="background:#533483;
                    height:5px;font-size:1px;line-height:1px;">&nbsp;</td>
                <td width="33%" style="background:#0f3460;
                    height:5px;font-size:1px;line-height:1px;">&nbsp;</td>
              </tr>
            </table>

            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:36px 36px 32px;text-align:center;">
                  <p style="font-family:Arial,sans-serif;
                             margin:0 0 8px 0;color:#e94560;
                             font-size:11px;font-weight:800;
                             text-transform:uppercase;
                             letter-spacing:3px;">
                    Issue #{issue} &nbsp;&middot;&nbsp; {date_str}
                  </p>
                  <h1 style="font-family:Arial,sans-serif;
                             margin:0 0 10px 0;color:#ffffff;
                             font-size:42px;font-weight:900;
                             letter-spacing:-1px;line-height:1;">
                    {NEWSLETTER_NAME}
                  </h1>
                  <p style="font-family:Arial,sans-serif;
                             margin:0 0 20px 0;color:#a8d8ea;
                             font-size:14px;line-height:1.6;">
                    {NEWSLETTER_TAGLINE}
                  </p>
                  <table width="60" cellpadding="0" cellspacing="0"
                         align="center" style="margin:0 auto 20px;">
                    <tr>
                      <td style="background:#e94560;height:3px;
                                 border-radius:2px;font-size:1px;
                                 line-height:1px;">&nbsp;</td>
                    </tr>
                  </table>
                  <p style="font-family:Arial,sans-serif;
                             margin:0;color:#8892b0;font-size:12px;">
                    Curated from Reddit &middot; Google News &middot;
                    YouTube &middot; LinkedIn &middot; Pinterest &middot;
                    Medium &middot; PM Blogs
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr><td style="height:20px;">&nbsp;</td></tr>

        <!-- ══ THIS WEEK'S SOURCES ══ -->
        <tr>
          <td style="background:#16213e;border-radius:14px;
                     padding:18px 24px;border:1px solid #0f3460;">
            <p style="font-family:Arial,sans-serif;
                       margin:0 0 10px 0;color:#a8b2d8;
                       font-size:11px;font-weight:800;
                       text-transform:uppercase;
                       letter-spacing:1.5px;">
              This week's sources
            </p>
            {pills}
          </td>
        </tr>

        <tr><td style="height:20px;">&nbsp;</td></tr>

        <!-- ══ INTRO NOTE ══ -->
        <tr>
          <td style="background:#ffffff;border-radius:14px;
                     padding:22px 24px;
                     border-left:5px solid #e94560;">
            <p style="font-family:Arial,sans-serif;
                       margin:0 0 10px 0;font-size:15px;
                       line-height:1.7;color:#222222;
                       font-weight:700;">
              Hey there! Welcome to this week's edition of
              Scope Creep.
            </p>
            <p style="font-family:Arial,sans-serif;
                       margin:0;font-size:14px;
                       line-height:1.7;color:#444444;">
              Your weekly dose of the best product management reads,
              handpicked by AI and curated for PM professionals.
              Here are your top 5 for this week.
            </p>
          </td>
        </tr>

        <tr><td style="height:28px;">&nbsp;</td></tr>

        <!-- ══ ARTICLE CARDS ══ -->
        <tr>
          <td>
            {cards_html}
          </td>
        </tr>

        <!-- ══ FOOTER ══ -->
        <tr>
          <td style="background:#16213e;border-radius:14px;
                     padding:28px 24px;text-align:center;
                     border-top:3px solid #e94560;">
            <p style="font-family:Arial,sans-serif;
                       margin:0 0 8px 0;color:#a8b2d8;
                       font-size:13px;font-weight:600;">
              You're receiving this because you subscribed to
              {NEWSLETTER_NAME}.
            </p>
            <p style="font-family:Arial,sans-serif;
                       margin:0;color:#8892b0;font-size:11px;
                       line-height:1.8;">
              Pioneered by Koushik &nbsp;&middot;&nbsp;
              Curated by AI &nbsp;&middot;&nbsp;
              Powered by Claude Haiku &amp; Buttondown
              &nbsp;&middot;&nbsp;
              Built on GitHub Actions
            </p>
          </td>
        </tr>

        <tr><td style="height:24px;">&nbsp;</td></tr>

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
