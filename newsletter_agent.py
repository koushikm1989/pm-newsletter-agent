import feedparser
import anthropic
import requests
import os
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── NEWSLETTER CONFIG ─────────────────────────────────────────────────────────

NEWSLETTER_NAME    = "Scope Creep"
NEWSLETTER_TAGLINE = "Top 5 product management reads, curated by AI. Fresh every Sunday."
START_DATE         = datetime(2026, 4, 30)

# Replace after MailerLite setup (Step 2 below tells you where each comes from)
MAILERLITE_SUBSCRIBE_URL = "https://dashboard.mailerlite.com/forms/190360336721774303/content"
MAILERLITE_GROUP_ID      = "190360180433618205"
MAILERLITE_FROM_EMAIL    = "mukherjee.koushik89@gmail.com"
MAILERLITE_FROM_NAME     = "Koushik Mukherjee"

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
    "https://news.google.com/rss/search?q=artificial+intelligence+breakthrough&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=science+discovery&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=technology+innovation&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=education+future+learning&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=sports+inspiring+comeback&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=motivational+success+story&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=startup+founder+story&hl=en-IN&gl=IN&ceid=IN:en",
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

# ── POOL METADATA (vibrant palette) ───────────────────────────────────────────

POOL_META = {
    "Reddit":      {"color": "#ff4500", "emoji": "👾", "bg": "#fff3ee", "border": "#ffc4ac"},
    "Google News": {"color": "#1a73e8", "emoji": "📰", "bg": "#eef4ff", "border": "#a8c4f8"},
    "Medium":      {"color": "#1a1a1a", "emoji": "✍️", "bg": "#f4f4f4", "border": "#cfcfcf"},
    "Blog":        {"color": "#0f5bbf", "emoji": "📝", "bg": "#eaf2ff", "border": "#93bbf5"},
    "LinkedIn":    {"color": "#0077b5", "emoji": "💼", "bg": "#e9f5fb", "border": "#7ec8e3"},
    "Pinterest":   {"color": "#c8083a", "emoji": "📌", "bg": "#ffeef1", "border": "#f5a0b0"},
    "YouTube":     {"color": "#cc0000", "emoji": "▶️", "bg": "#fff0f0", "border": "#ffaaaa"},
    "Unknown":     {"color": "#444444", "emoji": "🔗", "bg": "#f5f5f5", "border": "#cccccc"},
}

# Brand palette for the vibrant template
BRAND = {
    "ink":      "#15103a",   # deep indigo background
    "panel":    "#1f1850",   # raised panel
    "card":     "#ffffff",   # card surface
    "accent1":  "#ff5d73",   # coral/pink
    "accent2":  "#7c5cff",   # violet
    "accent3":  "#23d5ab",   # mint
    "sun":      "#ffc24b",   # amber
    "text":     "#2a2540",   # body text on white
    "muted":    "#b9b4e0",   # muted lavender on dark
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


def strip_emdashes(text: str) -> str:
    text = text.replace(" — ", ", ").replace("—", ", ")
    text = text.replace(" – ", ", ").replace("–", "-")
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def to_unicode_bold(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if 0x41 <= o <= 0x5A:
            out.append(chr(o + 0x1D593))
        elif 0x61 <= o <= 0x7A:
            out.append(chr(o + 0x1D58D))
        elif 0x30 <= o <= 0x39:
            out.append(chr(o + 0x1D7BC))
        else:
            out.append(ch)
    return "".join(out)


def to_unicode_italic(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if 0x41 <= o <= 0x5A:
            out.append(chr(o + 0x1D5C7))
        elif 0x61 <= o <= 0x7A:
            out.append(chr(o + 0x1D5C1))
        else:
            out.append(ch)
    return "".join(out)


def apply_linkedin_formatting(text: str) -> str:
    text = text.replace("-> ", "→ ").replace("->", "→")
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: to_unicode_bold(m.group(1)), text)
    text = re.sub(r"\*(.+?)\*", lambda m: to_unicode_italic(m.group(1)), text)
    return text


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

def call_claude(client, prompt: str, max_tokens: int):
    for attempt in range(3):
        try:
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            if "overloaded" in str(e).lower() and attempt < 2:
                print(f"  Anthropic overloaded, retrying in 30s... (attempt {attempt+1})")
                time.sleep(30)
            else:
                raise


def pick_and_summarise(client, articles, source_label, already_picked) -> dict:
    candidates = [a for a in articles if a["link"] not in already_picked]
    if not candidates:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\nURL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(candidates[:20])
    ])

    prompt = f"""You are the editor of Scope Creep, a Product Management newsletter, written in the voice of Koushik Mukherjee (a Lead Product Owner).

Source pool: {source_label}
Today: {datetime.now().strftime('%B %d, %Y')}

Pick the SINGLE most valuable article for a PM audience.
Prioritise: actionable insight, AI in product, career growth, or a genuinely witty or motivational angle.
Avoid: low-effort posts, generic news.

{numbered}

Write a summary of 3 to 4 sentences in Koushik's voice:
- Human and conversational, first person where it fits, a little opinionated.
- Explain what the article is about and 2 takeaways a PM would care about.
- End on why it matters right now.
- NEVER use em dashes or en dashes. Use commas and full stops. Keep sentences short.
- No corporate jargon. This is a newsletter summary, not a LinkedIn post.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

SUMMARY:
[3-4 sentence summary in Koushik's voice]"""

    message = call_claude(client, prompt, 600)
    text = message.content[0].text
    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            picked_index = idx
    return {"article": candidates[picked_index], "response": text}


def curate_five(client, all_pools: dict) -> list[dict]:
    results = []
    picked  = []
    pools_in_order = [
        ("REDDIT",                         all_pools["reddit"]),
        ("GOOGLE NEWS",                    all_pools["google"]),
        ("YOUTUBE / LINKEDIN / PINTEREST", all_pools["new"]),
        ("MEDIUM / BLOGS",                 all_pools["other"]),
        ("ALL SOURCES wildcard",           all_pools["all"]),
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


def get_summary(result: dict) -> str:
    m = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", result["response"])
    return strip_emdashes(m.group(1).strip()) if m else ""


# ── VIBRANT HTML NEWSLETTER (MailerLite web + email) ──────────────────────────

def build_newsletter_html(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    issue    = get_issue_number()

    section_labels = [
        ("🔥", "Top Pick"),
        ("📡", "In the News"),
        ("🎬", "Watch & Learn"),
        ("📖", "Deep Read"),
        ("💡", "Wildcard"),
    ]
    accents = [BRAND["accent1"], BRAND["accent2"], BRAND["accent3"], BRAND["sun"], BRAND["accent1"]]

    cards = []
    for i, result in enumerate(results):
        article = result["article"]
        pool    = article.get("pool", "Unknown")
        meta    = POOL_META.get(pool, POOL_META["Unknown"])
        emoji_s, label = section_labels[i] if i < len(section_labels) else ("✨", f"Pick {i+1}")
        accent  = accents[i % len(accents)]
        summary_html = get_summary(result).replace("\n", "<br>")

        img_html = ""
        if article.get("image"):
            img_html = f"""
            <tr><td style="padding:0 0 18px 0;line-height:0;">
              <img src="{article['image']}" width="100%" alt=""
                   style="display:block;width:100%;max-height:230px;
                          object-fit:cover;border-radius:14px;">
            </td></tr>"""

        cards.append(f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin:0 0 22px 0;background:{BRAND['card']};
              border-radius:18px;overflow:hidden;
              box-shadow:0 10px 30px rgba(20,16,58,0.18);">
  <tr>
    <td style="height:6px;background:{accent};font-size:1px;line-height:1px;">&nbsp;</td>
  </tr>
  <tr>
    <td style="padding:22px 24px 24px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
        <tr>
          <td>
            <span style="font-family:'Trebuchet MS',Verdana,sans-serif;
                         background:{accent};color:#ffffff;font-size:12px;
                         font-weight:bold;padding:5px 14px;border-radius:30px;
                         letter-spacing:0.4px;">
              {emoji_s} {label}
            </span>
          </td>
          <td align="right">
            <span style="font-family:'Trebuchet MS',Verdana,sans-serif;
                         background:{meta['bg']};color:{meta['color']};
                         border:1px solid {meta['border']};font-size:11px;
                         font-weight:bold;padding:4px 11px;border-radius:30px;">
              {meta['emoji']} {pool}
            </span>
          </td>
        </tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0">
        {img_html}
        <tr>
          <td style="padding-bottom:10px;">
            <a href="{article['link']}" target="_blank"
               style="font-family:Georgia,'Times New Roman',serif;
                      color:{BRAND['text']};text-decoration:none;
                      font-size:21px;line-height:1.3;font-weight:bold;">
              {article['title']}
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:14px;">
            <span style="font-family:'Trebuchet MS',Verdana,sans-serif;
                         font-size:12px;color:#8a85a6;">
              {article['source'][:60]}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:0 0 18px 0;">
            <p style="font-family:Verdana,Geneva,sans-serif;margin:0;
                      font-size:15px;line-height:1.75;color:{BRAND['text']};">
              {summary_html}
            </p>
          </td>
        </tr>
        <tr>
          <td>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:{accent};border-radius:10px;">
                  <a href="{article['link']}" target="_blank"
                     style="font-family:'Trebuchet MS',Verdana,sans-serif;
                            display:inline-block;color:#ffffff !important;
                            font-size:14px;font-weight:bold;padding:12px 26px;
                            text-decoration:none;border-radius:10px;">
                    Read the full article →
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
        f'<span style="font-family:Trebuchet MS,Verdana,sans-serif;'
        f'display:inline-block;background:{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]};'
        f'color:#ffffff;font-size:12px;font-weight:bold;padding:5px 13px;'
        f'border-radius:30px;margin:3px 4px;">'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["emoji"]} '
        f'{r["article"].get("pool","Unknown")}</span>'
        for r in results
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{NEWSLETTER_NAME} Issue #{issue}</title>
</head>
<body style="margin:0;padding:0;background:{BRAND['ink']};">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND['ink']};">
  <tr>
    <td align="center" style="padding:30px 14px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;">

        <!-- HERO -->
        <tr>
          <td style="background:{BRAND['panel']};border-radius:22px;
                     padding:0;overflow:hidden;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="25%" style="background:{BRAND['accent1']};height:8px;font-size:1px;line-height:1px;">&nbsp;</td>
                <td width="25%" style="background:{BRAND['accent2']};height:8px;font-size:1px;line-height:1px;">&nbsp;</td>
                <td width="25%" style="background:{BRAND['accent3']};height:8px;font-size:1px;line-height:1px;">&nbsp;</td>
                <td width="25%" style="background:{BRAND['sun']};height:8px;font-size:1px;line-height:1px;">&nbsp;</td>
              </tr>
            </table>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:40px 36px 34px 36px;text-align:center;">
                  <p style="font-family:'Trebuchet MS',Verdana,sans-serif;
                            margin:0 0 10px 0;color:{BRAND['sun']};
                            font-size:12px;font-weight:bold;
                            text-transform:uppercase;letter-spacing:3px;">
                    Issue #{issue} &nbsp;•&nbsp; {date_str}
                  </p>
                  <h1 style="font-family:Georgia,'Times New Roman',serif;
                             margin:0 0 12px 0;color:#ffffff;font-size:46px;
                             font-weight:bold;letter-spacing:-1px;line-height:1;">
                    {NEWSLETTER_NAME}
                  </h1>
                  <p style="font-family:Verdana,sans-serif;margin:0;
                            color:{BRAND['muted']};font-size:15px;line-height:1.6;">
                    {NEWSLETTER_TAGLINE}
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr><td style="height:18px;">&nbsp;</td></tr>

        <!-- SOURCES STRIP -->
        <tr>
          <td style="background:{BRAND['panel']};border-radius:16px;padding:16px 22px;text-align:center;">
            <p style="font-family:'Trebuchet MS',Verdana,sans-serif;margin:0 0 9px 0;
                      color:{BRAND['muted']};font-size:11px;font-weight:bold;
                      text-transform:uppercase;letter-spacing:1.5px;">
              This week's sources
            </p>
            <div>{pills}</div>
          </td>
        </tr>

        <tr><td style="height:18px;">&nbsp;</td></tr>

        <!-- INTRO -->
        <tr>
          <td style="background:{BRAND['card']};border-radius:16px;
                     padding:24px 26px;border-left:6px solid {BRAND['accent1']};">
            <p style="font-family:Georgia,serif;margin:0 0 10px 0;font-size:17px;
                      line-height:1.6;color:{BRAND['text']};font-weight:bold;">
              Hey there! Welcome to this week's Scope Creep.
            </p>
            <p style="font-family:Verdana,sans-serif;margin:0;font-size:14px;
                      line-height:1.7;color:{BRAND['text']};">
              Your weekly dose of the best product management reads, handpicked by AI
              and curated for PM professionals. Here are your top 5 for this week.
            </p>
          </td>
        </tr>

        <tr><td style="height:26px;">&nbsp;</td></tr>

        <!-- CARDS -->
        <tr><td>{cards_html}</td></tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:{BRAND['panel']};border-radius:16px;
                     padding:28px 24px;text-align:center;">
            <p style="font-family:'Trebuchet MS',Verdana,sans-serif;margin:0 0 8px 0;
                      color:#ffffff;font-size:14px;font-weight:bold;">
              Enjoyed this? Forward it to a fellow PM.
            </p>
            <p style="font-family:Verdana,sans-serif;margin:0 0 14px 0;
                      color:{BRAND['muted']};font-size:12px;line-height:1.7;">
              Pioneered by Koushik • Curated by AI • Powered by Claude Haiku & MailerLite
            </p>
            <p style="font-family:Verdana,sans-serif;margin:0;color:#6f6a90;font-size:11px;">
              You're receiving this because you subscribed to {NEWSLETTER_NAME}.<br>
              {{$unsubscribe}}
            </p>
          </td>
        </tr>

        <tr><td style="height:20px;">&nbsp;</td></tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ── MAILERLITE API ────────────────────────────────────────────────────────────

def send_to_mailerlite(html: str, results: list[dict]) -> bool:
    """Create a draft campaign in MailerLite via API."""
    api_key  = os.environ["MAILERLITE_API_KEY"]
    issue    = get_issue_number()
    date_str = datetime.now().strftime("%B %d, %Y")
    subject  = f"{NEWSLETTER_NAME} #{issue} | Top {len(results)} PM Reads | {date_str}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    payload = {
        "name":    subject,
        "type":    "regular",
        "emails": [{
            "subject":   subject,
            "from_name": MAILERLITE_FROM_NAME,
            "from":      MAILERLITE_FROM_EMAIL,
            "content":   html,
        }],
        "groups": [MAILERLITE_GROUP_ID],
    }

    resp = requests.post(
        "https://connect.mailerlite.com/api/campaigns",
        headers=headers, json=payload, timeout=30,
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        print(f"  MailerLite draft campaign created. ID: {data.get('id')}")
        print(f"  Subject: {subject}")
        print(f"  Review and send from your MailerLite dashboard (Campaigns).")
        return True
    print(f"  MailerLite API error {resp.status_code}: {resp.text}")
    return False


# ── LINKEDIN TRAILER (.txt, paste-ready) ──────────────────────────────────────

def build_linkedin_txt(client, results: list[dict]) -> str:
    issue    = get_issue_number()
    date_str = datetime.now().strftime("%B %d, %Y")

    listing = "\n\n".join([
        f"[{i+1}] Title: {r['article']['title']}\n"
        f"Source: {r['article']['source']}\n"
        f"URL: {r['article']['link']}\n"
        f"Summary: {r['article'].get('summary', '') or 'n/a'}"
        for i, r in enumerate(results)
    ])

    prompt = f"""You are writing a LinkedIn newsletter "trailer" in the voice of Koushik Mukherjee, a Lead Product Owner (B2B SaaS).

Today: {date_str}. This is the LinkedIn companion to the full Scope Creep email newsletter.
Its job: hook PM readers with ONE article unpacked in full, tease the rest, and drive them to subscribe to the full edition.

This week's 5 curated articles:

{listing}

TASKS:
1. Choose the SINGLE most compelling article to expand.
2. Write a punchy HEADLINE for it.
3. Write a DEEPDIVE of 150 to 220 words in Koushik's voice:
   - Bold one-line thesis to open, often a contrast.
   - Decode the insight, name the tension, cite numbers only if they appear in the summary.
   - Use -> arrow bullets for any 2 to 4 point list.
   - Mark 1 to 2 key phrases for bold with **double asterisks**, at most one phrase italic with *single asterisks*.
   - End with a genuine open question.
4. Write a one-line teaser for EACH of the OTHER four articles (not the expanded one).

VOICE RULES:
- First person, personal, optimistic, principled.
- NEVER use em dashes or en dashes. Use commas and full stops. Short sentences.
- No corporate jargon.

Respond in EXACTLY this format and nothing else:

EXPAND: [article number 1-5]
HEADLINE: [headline text, no asterisks]
DEEPDIVE:
[the 150-220 word deep dive]
TEASERS:
[n] one-line teaser for article n
[n] one-line teaser for article n
[n] one-line teaser for article n
[n] one-line teaser for article n"""

    raw = call_claude(client, prompt, 1200).content[0].text

    expand_m   = re.search(r"EXPAND:\s*\[?(\d+)\]?", raw)
    expand_idx = int(expand_m.group(1)) if expand_m else 1
    if not (1 <= expand_idx <= len(results)):
        expand_idx = 1

    headline_m = re.search(r"HEADLINE:\s*(.+)", raw)
    headline   = headline_m.group(1).strip().replace("*", "") if headline_m else results[expand_idx-1]["article"]["title"]

    deepdive_m = re.search(r"DEEPDIVE:\s*\n([\s\S]+?)\nTEASERS:", raw)
    deepdive   = deepdive_m.group(1).strip() if deepdive_m else ""

    teasers_block = raw.split("TEASERS:")[-1] if "TEASERS:" in raw else ""
    teasers       = re.findall(r"\[(\d+)\]\s*(.+)", teasers_block)

    expanded = results[expand_idx-1]["article"]
    hr = "━" * 24

    lines = []
    lines.append(f"{to_unicode_bold(NEWSLETTER_NAME)}   •   Issue #{issue}   •   {date_str}")
    lines.append("")
    lines.append("Your weekly trailer. The 5 best product reads of the week, with one unpacked in full below.")
    lines.append("")
    lines.append(hr)
    lines.append("")
    lines.append("🔍 " + to_unicode_bold("THIS WEEK'S DEEP DIVE"))
    lines.append("")
    lines.append(to_unicode_bold(strip_emdashes(headline)))
    lines.append("")
    lines.append(strip_emdashes(apply_linkedin_formatting(deepdive)))
    lines.append("")
    lines.append("Read it in full: " + expanded["link"])
    lines.append("")
    lines.append(hr)
    lines.append("")
    lines.append("📬 " + to_unicode_bold("ALSO IN THIS WEEK'S FULL EDITION"))
    lines.append("")
    for num, teaser in teasers:
        try:
            idx = int(num)
            if idx == expand_idx or not (1 <= idx <= len(results)):
                continue
            link = results[idx-1]["article"]["link"]
        except Exception:
            continue
        lines.append("→ " + strip_emdashes(teaser.strip().replace("*", "")))
        lines.append("   " + link)
        lines.append("")
    lines.append(hr)
    lines.append("")
    lines.append(to_unicode_bold("Get all 5, every Sunday."))
    lines.append("The full edition lands in your inbox each week. Subscribe to Scope Creep, free:")
    lines.append(MAILERLITE_SUBSCRIBE_URL)
    lines.append("")
    lines.append("#ProductManagement #AI #Newsletter #ScopeCreep #BuildInPublic")

    return "\n".join(lines)


def email_linkedin_txt(txt_content: str):
    sender    = os.environ["GMAIL_ADDRESS"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]
    issue     = get_issue_number()
    date_str  = datetime.now().strftime("%b %d, %Y")
    filename  = f"scope_creep_linkedin_issue_{issue}.txt"

    msg = MIMEMultipart()
    msg["Subject"] = f"\u270D\uFE0F Scope Creep #{issue} | LinkedIn newsletter draft | {date_str}"
    msg["From"] = sender
    msg["To"]   = recipient

    body = (
        "Hi Koushik,\n\n"
        f"Attached is your LinkedIn newsletter draft for Scope Creep #{issue}.\n\n"
        "It is paste ready. Open the .txt, copy everything, and paste it straight into the "
        "LinkedIn newsletter editor. Bold text and bullets are built with unicode so they "
        "survive the paste.\n\n"
        "This is the trailer. One article is unpacked in full, the other four are teasers that "
        "point readers to the full MailerLite edition so they subscribe.\n\n"
        "Have a good Sunday.\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEApplication(txt_content.encode("utf-8-sig"), _subtype="plain")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"  LinkedIn draft emailed as {filename}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/4 — Fetching all sources...")

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

    all_articles = reddit + google + linkedin + pinterest + youtube + medium + blogs
    print(f"  Total: {len(all_articles)} articles collected")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("\nStep 2/4 — Claude Haiku: curating the SAME top 5 for both outputs...")
    results = curate_five(client, {
        "reddit": reddit,
        "google": google,
        "new":    linkedin + pinterest + youtube,
        "other":  medium + blogs,
        "all":    all_articles,
    })
    print(f"  {len(results)} articles selected")

    if not results:
        print("No articles available. Exiting.")
        return

    print("\nStep 3/4 — MailerLite full edition (vibrant)...")
    try:
        html = build_newsletter_html(results)
        send_to_mailerlite(html, results)
    except Exception as e:
        print(f"  MailerLite step failed: {e}")

    print("\nStep 4/4 — LinkedIn trailer draft to Gmail...")
    try:
        txt = build_linkedin_txt(client, results)
        email_linkedin_txt(txt)
    except Exception as e:
        print(f"  LinkedIn step failed: {e}")

    print("\nDone!")


if __name__ == "__main__":
    main()
