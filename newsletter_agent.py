import feedparser
import anthropic
import requests
import os
import re
import time
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ── NEWSLETTER CONFIG ─────────────────────────────────────────────────────────

NEWSLETTER_NAME    = "Scope Creep"
NEWSLETTER_TAGLINE = "Top 5 product management reads, curated by AI. Fresh every Sunday."
START_DATE         = datetime(2026, 6, 21)   # Issue #1 launches this Sunday

MAILERLITE_GROUP_ID   = "190360180433618205"
MAILERLITE_FROM_EMAIL = "mukherjee.koushik89@gmail.com"
MAILERLITE_FROM_NAME  = "Koushik Mukherjee"
MAILERLITE_SUBSCRIBE_URL = "https://dashboard.mailerlite.com/forms/190360336721774303/content"

# Meme bank (public repo raw URLs)
GITHUB_RAW_BASE   = "https://raw.githubusercontent.com/koushikm1989/pm-newsletter-agent/main/memes"
MEME_HISTORY_FILE = "meme_history.json"
MEME_HISTORY_DAYS = 56  # don't repeat a meme within 8 weeks


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

# Subreddits scanned for a FRESH meme each week
MEME_SUBREDDIT_FEEDS = [
    "https://www.reddit.com/r/ProductManagement/.rss",
    "https://www.reddit.com/r/AIDankmemes/.rss",
    "https://www.reddit.com/r/ProgrammerHumor/.rss",
]

# ── POOL METADATA ─────────────────────────────────────────────────────────────

POOL_META = {
    "Reddit":      {"color": "#FF4500", "grad": "#FF6B35", "emoji": "👾", "bg": "#FFF3F0", "light": "#FFE0D6"},
    "Google News": {"color": "#1A73E8", "grad": "#4F9CF9", "emoji": "📰", "bg": "#EEF4FF", "light": "#D6E6FF"},
    "Medium":      {"color": "#1A1A1A", "grad": "#4A4A4A", "emoji": "✍️", "bg": "#F4F4F5", "light": "#E4E4E7"},
    "Blog":        {"color": "#7C3AED", "grad": "#A78BFA", "emoji": "📝", "bg": "#F5F0FF", "light": "#E9DDFF"},
    "LinkedIn":    {"color": "#0077B5", "grad": "#22A6E0", "emoji": "💼", "bg": "#EAF6FC", "light": "#CFEBF9"},
    "Pinterest":   {"color": "#E60023", "grad": "#FF4D6D", "emoji": "📌", "bg": "#FFF0F2", "light": "#FFD6DD"},
    "YouTube":     {"color": "#CC0000", "grad": "#FF3D3D", "emoji": "▶️", "bg": "#FFF1F1", "light": "#FFD9D9"},
    "Unknown":     {"color": "#475569", "grad": "#94A3B8", "emoji": "🔗", "bg": "#F8FAFC", "light": "#E2E8F0"},
}

SECTION_LABELS = [
    ("🔥", "TOP PICK",      "The one you can't miss this week"),
    ("📡", "IN THE NEWS",   "What the PM world is talking about"),
    ("🎬", "WATCH & LEARN", "Worth your Sunday watch time"),
    ("📖", "DEEP READ",     "Long form worth the time"),
    ("💡", "WILDCARD",      "Something unexpected, always worth it"),
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
FEEDPARSER_AGENT = HEADERS["User-Agent"]

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def strip_emdashes(text: str) -> str:
    text = text.replace(" — ", ", ").replace("—", ", ")
    text = text.replace(" – ", ", ").replace("–", "-")
    return re.sub(r"\s{2,}", " ", text).strip()


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
    text = re.sub(r"\*(.+?)\*",     lambda m: to_unicode_italic(m.group(1)), text)
    return text


def extract_image(entry) -> str:
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image") or \
               m.get("url", "").endswith(IMAGE_EXTS):
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


# ── MEME LOGIC ────────────────────────────────────────────────────────────────

def load_recent_meme_ids() -> set:
    if not os.path.exists(MEME_HISTORY_FILE):
        return set()
    try:
        with open(MEME_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        return set()
    cutoff = (datetime.now() - timedelta(days=MEME_HISTORY_DAYS)).strftime("%Y-%m-%d")
    return {e["id"] for e in history if e.get("date", "") >= cutoff}


def save_meme_id(meme_id: str):
    history = []
    if os.path.exists(MEME_HISTORY_FILE):
        try:
            with open(MEME_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    cutoff = (datetime.now() - timedelta(days=MEME_HISTORY_DAYS)).strftime("%Y-%m-%d")
    history = [e for e in history if e.get("date", "") >= cutoff]
    history.append({"date": datetime.now().strftime("%Y-%m-%d"), "id": meme_id})
    try:
        with open(MEME_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"  Could not write meme history: {e}")


def list_bank_memes() -> list[str]:
    if not os.path.isdir("memes"):
        return []
    return [
        f for f in os.listdir("memes")
        if f.lower().endswith(IMAGE_EXTS) and not f.startswith(".")
    ]


def fetch_meme_candidates() -> list[dict]:
    """Scan meme subreddits for image posts."""
    candidates = []
    cutoff = datetime.now() - timedelta(hours=72)
    for url in MEME_SUBREDDIT_FEEDS:
        try:
            feed = feedparser.parse(url, agent=FEEDPARSER_AGENT)
            for entry in feed.entries[:15]:
                try:
                    published = datetime(*entry.published_parsed[:6])
                    if published < cutoff:
                        continue
                except Exception:
                    pass
                img = extract_image(entry)
                if not img:
                    continue
                low = img.lower()
                # keep only true image hosts that render in email
                if ("i.redd.it" in low or "imgur" in low
                        or low.endswith(IMAGE_EXTS)):
                    candidates.append({
                        "title":  entry.get("title", "").strip(),
                        "image":  img,
                        "link":   entry.get("link", "").strip(),
                        "source": feed.feed.get("title", url),
                    })
        except Exception as e:
            print(f"  Meme RSS error ({url}): {e}")
    return candidates


def pick_live_meme(client, candidates, recent_ids) -> dict:
    """Ask Claude to pick the best on-brand meme, or return None."""
    fresh = [c for c in candidates if c["link"] not in recent_ids]
    if not fresh:
        return None

    listing = "\n".join([
        f"[{i+1}] {c['title']}" for i, c in enumerate(fresh[:20])
    ])

    prompt = f"""You are choosing one meme for a Product Management newsletter (audience: PMs, tech, AI professionals).

Below are meme post titles scraped from meme subreddits. Pick the SINGLE best one that is:
- Genuinely relevant to product management, tech, software, AI, or work/career humour
- Clean and professional enough for a LinkedIn-adjacent PM audience
- Actually funny, not low-effort

If NONE of them are relevant and appropriate for a PM audience, respond with exactly: NONE

Memes:
{listing}

Respond with ONLY the number of your pick (e.g. "3"), or "NONE". Nothing else."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        ans = msg.content[0].text.strip()
    except Exception as e:
        print(f"  Meme pick error: {e}")
        return None

    if ans.upper().startswith("NONE"):
        return None
    m = re.search(r"\d+", ans)
    if not m:
        return None
    idx = int(m.group()) - 1
    if 0 <= idx < len(fresh):
        return fresh[idx]
    return None


def select_meme(client) -> dict:
    """
    Returns dict:
      {image, caption, credit, id, mode}  where mode is 'live' or 'bank' or None
    """
    recent_ids = load_recent_meme_ids()

    # 1) Try a fresh, on-brand meme from Reddit
    candidates = fetch_meme_candidates()
    print(f"  Meme candidates found: {len(candidates)}")
    live = pick_live_meme(client, candidates, recent_ids)
    if live:
        print(f"  Live meme selected: {live['title'][:60]}")
        return {
            "image":   live["image"],
            "caption": live["title"],
            "credit":  f"via {live['source']}",
            "id":      live["link"],
            "mode":    "live",
        }

    # 2) Fall back to the meme bank (avoid recently used)
    bank = list_bank_memes()
    if bank:
        bank_ids = [f"bank:{f}" for f in bank]
        unused = [f for f in bank if f"bank:{f}" not in recent_ids]
        choice = random.choice(unused if unused else bank)
        print(f"  Bank meme selected: {choice}")
        return {
            "image":   f"{GITHUB_RAW_BASE}/{choice}",
            "caption": "Meme of the week",
            "credit":  "from the Scope Creep meme vault",
            "id":      f"bank:{choice}",
            "mode":    "bank",
        }

    # 3) Nothing available at all
    print("  No meme available (no live candidate and empty bank).")
    return {"image": None, "caption": "", "credit": "", "id": None, "mode": None}


# ── CLAUDE (articles) ─────────────────────────────────────────────────────────

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


def pick_and_summarise(client, candidates, source_label) -> dict:
    if not candidates:
        return None

    numbered = "\n\n".join([
        f"[{i+1}] Title: {a['title']}\n"
        f"Source: {a['source']}\nURL: {a['link']}\n"
        f"Summary: {a['summary'] or 'No summary available'}"
        for i, a in enumerate(candidates[:20])
    ])

    prompt = f"""You are the editor of Scope Creep, a Product Management newsletter written in the voice of Koushik Mukherjee (Lead Product Owner, B2B SaaS).

Source pool: {source_label}
Today: {datetime.now().strftime('%B %d, %Y')}

Pick the SINGLE most valuable article for a PM audience.
Prioritise: actionable insight, AI in product, career growth, motivational or witty angle from science, tech, sports, education.
Avoid: low-effort posts, generic news, clickbait.

{numbered}

Write a newsletter summary of 3 to 4 sentences in Koushik's voice:
- Human and conversational, first person where it fits, a little opinionated.
- Explain what the article is about and 2 takeaways a PM would care about.
- End on why it matters right now.
- NEVER use em dashes or en dashes. Use commas and full stops.
- No corporate jargon. Short sentences. No long hyphenated phrases.

Respond in EXACTLY this format:

PICK: [number]
Title: [title]
URL: [url]
Source: [source]
Why picked: [one sentence]

SUMMARY:
[3-4 sentence summary in Koushik's voice]"""

    message = call_claude(client, prompt, 700)
    text = message.content[0].text

    summary_match = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", text)
    summary = summary_match.group(1).strip() if summary_match else ""

    words = summary.split()
    ends_clean = summary.rstrip().endswith((".", "!", "?"))
    if len(words) < 25 or not ends_clean:
        print(f"  Rejected pick (incomplete summary, {len(words)} words). Skipping.")
        return None

    picked_index = 0
    match = re.search(r"PICK:\s*\[?(\d+)\]?", text)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(candidates):
            picked_index = idx
    return {"article": candidates[picked_index], "response": text}


def curate_five(client, all_pools: dict) -> list[dict]:
    results      = []
    picked_links = set()
    used_pools   = set()

    pools_in_order = [
        ("REDDIT",                         all_pools["reddit"]),
        ("GOOGLE NEWS",                    all_pools["google"]),
        ("YOUTUBE / LINKEDIN / PINTEREST", all_pools["new"]),
        ("MEDIUM / BLOGS",                 all_pools["other"]),
        ("ALL SOURCES — wildcard",         all_pools["all"]),
    ]

    def candidates_from(pool):
        return [
            a for a in pool
            if a["link"] not in picked_links
            and a.get("pool") not in used_pools
        ]

    for label, pool in pools_in_order:
        if len(results) >= 5:
            break
        cands = candidates_from(pool)
        for _ in range(3):
            if not cands:
                break
            result = pick_and_summarise(client, cands, label)
            if result:
                results.append(result)
                picked_links.add(result["article"]["link"])
                used_pools.add(result["article"].get("pool"))
                break
            cands = cands[1:]

    if len(results) < 5:
        cands = candidates_from(all_pools["all"])
        seen = set()
        unique_pool_cands = []
        for a in cands:
            if a.get("pool") not in seen:
                unique_pool_cands.append(a)
                seen.add(a.get("pool"))
        for a in unique_pool_cands:
            if len(results) >= 5:
                break
            result = pick_and_summarise(client, [a], "FILL — distinct source")
            if result:
                results.append(result)
                picked_links.add(result["article"]["link"])
                used_pools.add(result["article"].get("pool"))

    print(f"  Distinct sources used: {', '.join(sorted(p for p in used_pools if p))}")
    return results


# ── MAILERLITE HTML — VIBRANT AURORA DESIGN ──────────────────────────────────

def build_newsletter_html(results: list[dict], meme: dict) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    issue    = get_issue_number()
    day_name = datetime.now().strftime("%A")

    cards = []
    for i, result in enumerate(results):
        article  = result["article"]
        response = result["response"]
        pool     = article.get("pool", "Unknown")
        meta     = POOL_META.get(pool, POOL_META["Unknown"])
        color    = meta["color"]
        grad     = meta["grad"]
        light    = meta["light"]

        sec_emoji, sec_label, sec_sub = SECTION_LABELS[i] \
            if i < len(SECTION_LABELS) else ("📄", f"PICK {i+1}", "")

        summary_match = re.search(r"SUMMARY:\s*\n([\s\S]+?)(?:\n---|\Z)", response)
        summary       = summary_match.group(1).strip() if summary_match else ""
        summary       = strip_emdashes(summary)
        summary_html  = summary.replace("\n", "<br>")

        media_html = ""
        if article.get("image"):
            media_html = f"""
            <tr>
              <td style="padding:0;line-height:0;">
                <img src="{article['image']}" width="100%"
                     style="display:block;width:100%;height:240px;
                            object-fit:cover;" alt="">
              </td>
            </tr>"""

        source_label = article["source"][:50] if article.get("source") else pool

        cards.append(f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-bottom:36px;border-radius:22px;overflow:hidden;
              background:#ffffff;box-shadow:0 12px 40px rgba(15,23,42,0.18);">
  <tr>
    <td style="background:linear-gradient(100deg,{color} 0%,{grad} 100%);
               padding:16px 30px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         color:#ffffff;font-size:12px;font-weight:800;
                         letter-spacing:2.5px;text-transform:uppercase;">
              {sec_emoji}&nbsp;&nbsp;{sec_label}
            </span><br>
            <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                         color:rgba(255,255,255,0.80);font-size:11px;">
              {sec_sub}
            </span>
          </td>
          <td align="right">
            <span style="font-family:Arial,sans-serif;
                         background:rgba(255,255,255,0.22);
                         color:#ffffff;font-size:11px;font-weight:700;
                         padding:4px 12px;border-radius:20px;">
              {meta['emoji']}&nbsp;{pool}
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  {media_html}
  <tr>
    <td style="padding:30px 30px 26px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding-bottom:12px;">
            <h2 style="font-family:Georgia,serif;margin:0;font-size:24px;
                       line-height:1.3;font-weight:700;color:#0F172A;">
              <a href="{article['link']}" target="_blank"
                 style="color:#0F172A;text-decoration:none;">{article['title']}</a>
            </h2>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:20px;">
            <span style="font-family:Arial,sans-serif;display:inline-block;
                         background:{light};color:{color};font-size:11px;
                         font-weight:800;padding:5px 14px;border-radius:8px;
                         letter-spacing:0.4px;">
              {source_label}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:4px 0 24px 18px;border-left:4px solid {color};">
            <p style="font-family:Georgia,serif;margin:0;font-size:16px;
                      line-height:1.9;color:#334155;">
              {summary_html}
            </p>
          </td>
        </tr>
        <tr>
          <td>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:linear-gradient(100deg,{color},{grad});
                           border-radius:12px;">
                  <a href="{article['link']}" target="_blank"
                     style="font-family:'Trebuchet MS',Arial,sans-serif;
                            display:inline-block;color:#ffffff !important;
                            font-size:14px;font-weight:800;padding:14px 30px;
                            text-decoration:none;border-radius:12px;
                            letter-spacing:0.4px;">
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

    # ── Meme of the week card ─────────────────────────────────────────────────
    meme_html = ""
    if meme and meme.get("image"):
        caption = strip_emdashes(meme.get("caption", ""))[:140]
        credit  = meme.get("credit", "")
        meme_html = f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-bottom:36px;border-radius:22px;overflow:hidden;
              background:#ffffff;box-shadow:0 12px 40px rgba(15,23,42,0.18);">
  <tr>
    <td style="background:linear-gradient(100deg,#F59E0B 0%,#FF4500 100%);
               padding:16px 30px;">
      <span style="font-family:'Trebuchet MS',Arial,sans-serif;color:#ffffff;
                   font-size:12px;font-weight:800;letter-spacing:2.5px;
                   text-transform:uppercase;">😂&nbsp;&nbsp;MEME OF THE WEEK</span><br>
      <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                   color:rgba(255,255,255,0.85);font-size:11px;">
        Because every PM week needs one
      </span>
    </td>
  </tr>
  <tr>
    <td style="padding:0;line-height:0;">
      <img src="{meme['image']}" width="100%"
           style="display:block;width:100%;max-height:520px;
                  object-fit:contain;background:#0F172A;" alt="Meme of the week">
    </td>
  </tr>
  <tr>
    <td style="padding:18px 30px 24px;text-align:center;">
      <p style="font-family:Georgia,serif;margin:0 0 6px;font-size:15px;
                line-height:1.5;color:#334155;font-style:italic;">
        {caption}
      </p>
      <p style="font-family:Arial,sans-serif;margin:0;font-size:11px;color:#94A3B8;">
        {credit}
      </p>
    </td>
  </tr>
</table>"""

    pills = "".join([
        f'<span style="font-family:Arial,sans-serif;display:inline-block;'
        f'background:linear-gradient(100deg,'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["color"]},'
        f'{POOL_META.get(r["article"].get("pool","Unknown"),POOL_META["Unknown"])["grad"]});'
        f'color:#ffffff;font-size:12px;font-weight:700;padding:6px 16px;'
        f'border-radius:20px;margin:4px 5px;">'
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
<body style="margin:0;padding:0;
             background:linear-gradient(160deg,#0B1020 0%,#1A1442 40%,#2D1B5E 70%,#0B1020 100%);">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:linear-gradient(160deg,#0B1020 0%,#1A1442 40%,#2D1B5E 70%,#0B1020 100%);">
  <tr>
    <td align="center" style="padding:36px 14px 56px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;">

        <tr>
          <td style="border-radius:26px;overflow:hidden;
                     background:linear-gradient(135deg,
                       #FF4500 0%,#E60080 28%,#7C3AED 60%,#1A73E8 100%);
                     padding:3px;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:linear-gradient(150deg,#10142C 0%,#1B1840 55%,#241654 100%);
                          border-radius:24px;">
              <tr>
                <td style="padding:52px 44px 46px;text-align:center;">
                  <div style="display:inline-block;margin-bottom:22px;
                              background:rgba(255,255,255,0.10);
                              border:1px solid rgba(245,158,11,0.45);
                              border-radius:24px;padding:7px 20px;">
                    <span style="font-family:'Trebuchet MS',Arial,sans-serif;
                                 color:#FBBF24;font-size:12px;font-weight:800;
                                 letter-spacing:3px;text-transform:uppercase;">
                      Issue #{issue} &nbsp;&bull;&nbsp; {date_str}
                    </span>
                  </div><br>
                  <h1 style="font-family:Georgia,serif;margin:0 0 14px;
                             color:#ffffff;font-size:60px;font-weight:700;
                             letter-spacing:-1.5px;line-height:1;
                             text-shadow:0 4px 24px rgba(124,58,237,0.55);">
                    {NEWSLETTER_NAME}
                  </h1>
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                             margin:0 0 26px;color:#C7D2FE;font-size:16px;
                             line-height:1.6;max-width:440px;display:inline-block;">
                    {NEWSLETTER_TAGLINE}
                  </p><br>
                  <div style="display:inline-block;height:3px;width:80px;
                              background:linear-gradient(90deg,#FF4500,#7C3AED,#1A73E8);
                              border-radius:3px;margin-bottom:22px;"></div><br>
                  <p style="font-family:Georgia,serif;margin:0;
                             color:#94A3B8;font-size:13px;font-style:italic;">
                    Happy {day_name}. Five hand-picked reads,
                    one from each corner of the product world.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr><td style="height:26px;">&nbsp;</td></tr>

        <tr>
          <td style="background:rgba(255,255,255,0.06);
                     border:1px solid rgba(255,255,255,0.10);
                     border-radius:18px;padding:22px 28px;text-align:center;">
            <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                       margin:0 0 14px;font-size:11px;color:#A5B4FC;
                       font-weight:800;text-transform:uppercase;
                       letter-spacing:2.5px;">
              This week's five sources
            </p>
            <div>{pills}</div>
          </td>
        </tr>

        <tr><td style="height:22px;">&nbsp;</td></tr>

        <tr>
          <td style="background:linear-gradient(135deg,#FEF3C7,#FFE4E6);
                     border-radius:18px;padding:26px 30px;
                     border-left:6px solid #F59E0B;">
            <p style="font-family:Georgia,serif;margin:0 0 10px;
                       font-size:19px;line-height:1.5;color:#1F2937;font-weight:700;">
              Hey there! Welcome to this week's Scope Creep. 👋
            </p>
            <p style="font-family:Georgia,serif;margin:0;
                       font-size:16px;line-height:1.75;color:#475569;">
              Your weekly dose of the best product management reads,
              handpicked by AI and curated for PM professionals.
              Here are your top 5 for this week, with a meme to close us out.
            </p>
          </td>
        </tr>

        <tr><td style="height:36px;">&nbsp;</td></tr>

        <tr><td>{cards_html}</td></tr>

        <tr><td>{meme_html}</td></tr>

        <tr>
          <td style="border-radius:22px;overflow:hidden;
                     background:linear-gradient(135deg,#7C3AED 0%,#E60080 55%,#FF4500 100%);
                     padding:3px;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:linear-gradient(150deg,#14102E,#241654);
                          border-radius:20px;">
              <tr>
                <td style="padding:40px 44px;text-align:center;">
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                             margin:0 0 8px;color:#DDD6FE;font-size:11px;
                             font-weight:800;letter-spacing:2.5px;
                             text-transform:uppercase;">
                    Enjoying Scope Creep?
                  </p>
                  <h2 style="font-family:Georgia,serif;margin:0 0 14px;
                             color:#ffffff;font-size:28px;font-weight:700;">
                    Share it. Grow the tribe.
                  </h2>
                  <p style="font-family:'Trebuchet MS',Arial,sans-serif;
                             margin:0 0 26px;color:#C4B5FD;font-size:15px;
                             line-height:1.6;">
                    Know a PM who'd love this? Send them the link.
                    It's free. Always will be.
                  </p>
                  <table cellpadding="0" cellspacing="0" align="center">
                    <tr>
                      <td style="background:linear-gradient(100deg,#FBBF24,#F59E0B);
                                 border-radius:14px;">
                        <a href="{MAILERLITE_SUBSCRIBE_URL}" target="_blank"
                           style="font-family:'Trebuchet MS',Arial,sans-serif;
                                  display:inline-block;color:#0F172A !important;
                                  font-size:15px;font-weight:800;padding:16px 38px;
                                  text-decoration:none;border-radius:14px;
                                  letter-spacing:0.4px;">
                          Subscribe to Scope Creep &rarr;
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr><td style="height:30px;">&nbsp;</td></tr>

        <tr>
          <td style="text-align:center;padding:20px 0;">
            <p style="font-family:Arial,sans-serif;color:#94A3B8;
                       font-size:12px;margin:0 0 6px;">
              You received this because you subscribed to Scope Creep.
            </p>
            <p style="font-family:Arial,sans-serif;color:#64748B;
                       font-size:11px;margin:0;line-height:1.8;">
              Pioneered by Koushik &nbsp;&middot;&nbsp; Curated by AI &nbsp;&middot;&nbsp;
              Powered by Claude Haiku &amp; MailerLite &nbsp;&middot;&nbsp;
              Built on GitHub Actions
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ── MAILERLITE API (DRAFT ONLY) ──────────────────────────────────────────────

def _ml_headers():
    return {
        "Authorization": f"Bearer {os.environ['MAILERLITE_API_KEY']}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def create_mailerlite_draft(html: str, results: list[dict]) -> str:
    """Create a DRAFT campaign only. Never auto-sends. Returns campaign_id."""
    issue    = get_issue_number()
    date_str = datetime.now().strftime("%B %d, %Y")
    subject  = f"{NEWSLETTER_NAME} #{issue} | Top {len(results)} PM Reads | {date_str}"

    from_email = MAILERLITE_FROM_EMAIL.strip()
    if not from_email or "@" not in from_email:
        print("  ERROR: MAILERLITE_FROM_EMAIL is not valid.")
        return None

    payload = {
        "type":        "regular",
        "name":        f"Scope Creep #{issue} - {date_str}",
        "language_id": 4,
        "emails": [
            {
                "subject":   subject,
                "from_name": MAILERLITE_FROM_NAME,
                "from":      from_email,
                "content":   html,
            }
        ],
        "groups": [str(MAILERLITE_GROUP_ID)],
    }

    resp = requests.post(
        "https://connect.mailerlite.com/api/campaigns",
        headers=_ml_headers(), json=payload, timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  MailerLite create error {resp.status_code}: {resp.text}")
        return None

    campaign_id = resp.json()["data"]["id"]
    print(f"  Draft campaign created. ID: {campaign_id}")
    print(f"  Subject: {subject}")
    print("  NOTE: This is a DRAFT. Review and send manually from MailerLite.")
    return campaign_id


# ── LINKEDIN TRAILER + NOTIFICATION EMAIL ────────────────────────────────────

def build_linkedin_txt(client, results: list[dict]) -> str:
    issue    = get_issue_number()
    date_str = datetime.now().strftime("%B %d, %Y")

    listing = "\n\n".join([
        f"[{i+1}] Title: {r['article']['title']}\n"
        f"Source: {r['article']['source']}\n"
        f"URL: {r['article']['link']}\n"
        f"Summary: {r['article'].get('summary','') or 'n/a'}"
        for i, r in enumerate(results)
    ])

    prompt = f"""You are writing a LinkedIn newsletter "trailer" in the voice of Koushik Mukherjee, a Lead Product Owner (B2B SaaS).

Today: {date_str}. This is the LinkedIn companion to Scope Creep, a full email newsletter.
Its job: hook PM readers with ONE article unpacked in full, tease the rest, and drive them to subscribe.

This week's 5 curated articles:

{listing}

TASKS:
1. Choose the SINGLE most compelling article to expand.
2. Write a punchy HEADLINE for it.
3. Write a DEEPDIVE of 150 to 220 words in Koushik's voice:
   - Bold one-line thesis to open, often a contrast.
   - Decode the insight, name the tension, cite numbers only if in the summary.
   - Use -> arrow bullets for any 2 to 4 point list.
   - Mark 1 to 2 key phrases for bold with **double asterisks**.
   - End with a genuine open question.
4. Write a one-line teaser for EACH of the OTHER four articles.

VOICE RULES:
- First person, personal, optimistic, principled.
- NEVER use em dashes or en dashes. Use commas and full stops.
- No corporate jargon. Short sentences.

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
    headline   = (headline_m.group(1).strip().replace("*", "")
                  if headline_m else results[expand_idx - 1]["article"]["title"])

    deepdive_m = re.search(r"DEEPDIVE:\s*\n([\s\S]+?)\nTEASERS:", raw)
    deepdive   = deepdive_m.group(1).strip() if deepdive_m else ""

    teasers_block = raw.split("TEASERS:")[-1] if "TEASERS:" in raw else ""
    teasers       = re.findall(r"\[(\d+)\]\s*(.+)", teasers_block)

    expanded = results[expand_idx - 1]["article"]
    hr       = "━" * 24

    lines = []
    lines.append(f"{to_unicode_bold(NEWSLETTER_NAME)}   \u2022   Issue #{issue}   \u2022   {date_str}")
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
            link = results[idx - 1]["article"]["link"]
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


def email_linkedin_txt(txt_content: str, meme: dict, campaign_id: str):
    sender    = os.environ["GMAIL_ADDRESS"]
    password  = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]
    issue     = get_issue_number()
    date_str  = datetime.now().strftime("%b %d, %Y")
    filename  = f"scope_creep_linkedin_issue_{issue}.txt"

    # Meme status line for the notification
    mode = meme.get("mode") if meme else None
    if mode == "live":
        meme_status = (
            "✅ MEME: A fresh meme was found from Reddit and added to the edition. "
            "Please confirm it renders correctly in the MailerLite preview before sending.\n"
        )
    elif mode == "bank":
        meme_status = (
            "📦 MEME: No fresh meme was found this week, so one was pulled from your "
            "meme bank. Review it in the MailerLite draft. If you want a different one, "
            "swap the image in MailerLite before sending.\n"
        )
    else:
        meme_status = (
            "⚠️ MEME: NO meme was found and the meme bank is empty. The edition has NO "
            "meme right now. Add a meme image to the MailerLite draft before sending, "
            "or upload one to the memes folder for next time.\n"
        )

    flag = "⚠️ ACTION NEEDED " if mode != "live" else ""
    subject_line = (
        f"\u270D\uFE0F {flag}Scope Creep #{issue} | Draft ready for review | {date_str}"
    )

    msg = MIMEMultipart()
    msg["Subject"] = subject_line
    msg["From"] = sender
    msg["To"]   = recipient

    cid = campaign_id or "(not created)"
    body = (
        f"Hi Koushik,\n\n"
        f"Scope Creep #{issue} is ready as a DRAFT in MailerLite. Nothing has been sent yet.\n\n"
        f"{meme_status}\n"
        f"To send: open MailerLite, go to Campaigns, find the draft (campaign ID {cid}), "
        f"review it, and hit send when happy.\n\n"
        "Attached is your LinkedIn trailer .txt. Copy it and paste straight into the "
        "LinkedIn newsletter editor. Unicode bold and bullets survive the paste cleanly.\n\n"
        "Happy Sunday.\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEApplication(txt_content.encode("utf-8-sig"), _subtype="plain")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"  Notification + LinkedIn draft emailed (meme mode: {mode}).")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("Step 1/5 — Fetching all sources...")

    reddit = fetch_rss(REDDIT_FEEDS)
    for a in reddit:
        a["pool"] = "Reddit"
    print(f"  Reddit: {len(reddit)}")

    google = fetch_rss(GOOGLE_NEWS_FEEDS, max_age_hours=168)
    for a in google:
        a["pool"] = "Google News"
    print(f"  Google News: {len(google)}")

    linkedin_rss = fetch_rss(LINKEDIN_RSS_FEEDS)
    for a in linkedin_rss:
        a["pool"] = "LinkedIn"
    print(f"  LinkedIn RSS: {len(linkedin_rss)}")

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

    all_articles = reddit + google + linkedin_rss + pinterest + youtube + medium + blogs
    print(f"  Total: {len(all_articles)} articles collected")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("\nStep 2/5 — Claude Haiku: curating top 5 (distinct sources)...")
    results = curate_five(client, {
        "reddit": reddit,
        "google": google,
        "new":    linkedin_rss + pinterest + youtube,
        "other":  medium + blogs,
        "all":    all_articles,
    })
    print(f"  {len(results)} articles selected")

    if not results:
        print("No articles available. Exiting.")
        return

    print("\nStep 3/5 — Selecting the meme of the week...")
    meme = select_meme(client)

    print("\nStep 4/5 — Building newsletter and creating MailerLite DRAFT...")
    campaign_id = None
    try:
        html = build_newsletter_html(results, meme)
        campaign_id = create_mailerlite_draft(html, results)
    except Exception as e:
        print(f"  MailerLite step failed: {e}")

    print("\nStep 5/5 — LinkedIn trailer + notification to Gmail...")
    try:
        txt = build_linkedin_txt(client, results)
        email_linkedin_txt(txt, meme, campaign_id)
    except Exception as e:
        print(f"  Notification step failed: {e}")

    # Record the meme so it isn't reused soon
    if meme and meme.get("id"):
        save_meme_id(meme["id"])

    print("\nDone!")


if __name__ == "__main__":
    main()
