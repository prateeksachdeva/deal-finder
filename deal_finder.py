import requests
from bs4 import BeautifulSoup
import os
import re

# ============================================================
#   CONFIGURATION — Loaded from GitHub Secrets automatically
# ============================================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
TOP_DEALS_COUNT     = 5
# ============================================================

# ────────────────────────────────────────────────────────────
# POPULAR INDIAN DEAL TELEGRAM CHANNELS
# These channels post real Amazon.in + Flipkart deals in ₹
# RSSHub converts them to RSS feed — works from ANYWHERE
# ────────────────────────────────────────────────────────────
DEAL_CHANNELS = [
    ("Loot Deals India",    "lootdealsindia"),
    ("Deals4India",         "Deals4India"),
    ("Amazon Deals India",  "amazondealsinindia"),
    ("Flipkart Offers",     "flipkartofferss"),
    ("India Loot",          "indialootofficial"),
    ("Deal Baba",           "dealbaba_in"),
    ("Loot Lo",             "lootlo"),
]

BLOG_SKIP_WORDS = [
    "top 10", "top 15", "top 20", "best deals of", "biggest sale",
    "how to", "guide", "tips", "ways to", "things you", "you should",
    "everything you", "what is", "why you"
]

def is_blog(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in BLOG_SKIP_WORDS)

def extract_discount(text: str) -> int:
    matches = re.findall(r'(\d{1,3})\s*%\s*off', text.lower())
    if matches:
        return max(int(m) for m in matches if 5 <= int(m) <= 95)
    matches2 = re.findall(r'(?:upto|flat|get|save)\s*(\d{1,3})\s*%', text.lower())
    if matches2:
        return max(int(m) for m in matches2 if 5 <= int(m) <= 95)
    return 0

def extract_prices_inr(text: str) -> list:
    prices = []
    for pattern in [r'₹\s*([\d,]+)', r'Rs\.?\s*([\d,]+)', r'INR\s*([\d,]+)']:
        for m in re.findall(pattern, text):
            try:
                val = int(m.replace(",", ""))
                if 50 < val < 5000000:
                    prices.append(val)
            except:
                pass
    return sorted(set(prices))

def calculate_discount(deal_price, original_price) -> int:
    if deal_price and original_price and original_price > deal_price:
        return int(((original_price - deal_price) / original_price) * 100)
    return 0

def get_platform(text: str) -> str:
    return "Flipkart" if "flipkart" in text.lower() else "Amazon India"

def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id"                : TELEGRAM_CHANNEL_ID,
            "text"                   : message,
            "parse_mode"             : "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        if r.status_code == 200:
            print("✅ Sent to Telegram!")
        else:
            print(f"❌ Telegram Error: {r.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")


# ────────────────────────────────────────────────────────────
# FETCH DEALS FROM TELEGRAM CHANNELS VIA RSSHUB
# RSSHub converts any public Telegram channel to RSS
# Works globally from any server including GitHub Actions
# ────────────────────────────────────────────────────────────
def fetch_telegram_channels() -> list:
    print("\n🔍 Reading Indian deal Telegram channels via RSSHub...")
    deals = []

    # RSSHub public instances — try each one
    rsshub_instances = [
        "https://rsshub.app",
        "https://rss.shab.fun",
        "https://rsshub.woodland.cafe",
    ]

    for channel_name, channel_id in DEAL_CHANNELS:
        fetched = False
        for instance in rsshub_instances:
            try:
                url      = f"{instance}/telegram/channel/{channel_id}"
                r        = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                soup     = BeautifulSoup(r.text, "xml")
                items    = soup.find_all("item")

                if not items:
                    continue

                print(f"   [{channel_name}] → {len(items)} posts")

                for item in items:
                    try:
                        title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                        link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                        desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                        combined = title + " " + desc

                        # Skip blog articles
                        if is_blog(title):
                            continue

                        # Must mention Amazon or Flipkart
                        if "amazon" not in combined.lower() and "flipkart" not in combined.lower():
                            continue

                        # Must have price in ₹ or discount %
                        has_price    = bool(re.search(r'₹|rs\.|inr', combined.lower()))
                        has_discount = bool(re.search(r'\d+\s*%\s*off', combined.lower()))
                        if not has_price and not has_discount:
                            continue

                        discount = extract_discount(combined)
                        prices   = extract_prices_inr(combined)
                        deal_price     = prices[0]  if len(prices) >= 1 else None
                        original_price = prices[-1] if len(prices) >= 2 else None

                        if discount == 0 and deal_price and original_price:
                            discount = calculate_discount(deal_price, original_price)

                        # Use description as title if title is empty/generic
                        display_title = desc[:80] if len(title) < 10 else title[:80]

                        deals.append({
                            "title"         : display_title,
                            "link"          : link,
                            "discount"      : discount,
                            "deal_price"    : deal_price,
                            "original_price": original_price,
                            "platform"      : get_platform(combined),
                            "source"        : channel_name
                        })

                    except:
                        continue

                fetched = True
                break  # Stop trying other instances if this one worked

            except Exception as e:
                continue

        if not fetched:
            print(f"   ❌ Could not fetch {channel_name}")

    print(f"\n   ✅ Total real deals collected: {len(deals)}")
    return deals


# ────────────────────────────────────────────────────────────
# SEND TOP 5 AS ONE CLEAN MESSAGE
# ────────────────────────────────────────────────────────────
def send_top5(deals: list):
    medals  = ["🥇", "🥈", "🥉", "🔥", "💥"]
    message = "🇮🇳 <b>TOP 5 DEALS — Amazon India &amp; Flipkart</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, deal in enumerate(deals):
        medal = medals[i] if i < len(medals) else "🔥"
        message += f"{medal} <b>#{i+1} — {deal['platform']}</b>\n"
        message += f"📦 {deal['title']}\n"

        if deal['original_price'] and deal['deal_price'] and deal['original_price'] != deal['deal_price']:
            message += f"🏷️ MRP: <s>₹{deal['original_price']:,}</s>  💰 <b>₹{deal['deal_price']:,}</b>\n"
        elif deal['deal_price']:
            message += f"💰 Price: <b>₹{deal['deal_price']:,}</b>\n"

        if deal['discount'] > 0:
            message += f"📉 You Save: <b>{deal['discount']}% OFF</b>\n"

        message += f"🛒 <a href='{deal['link']}'>Buy Now →</a>\n"
        message += f"📡 Via: {deal['source']}\n"
        message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += "⏰ <i>Next scan in 6 hours!</i>"
    send_to_telegram(message)


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*50)
    print("🚀 India Deal Finder — Telegram Channels Method!")
    print(f"   Source    : Indian Deal Telegram Channels")
    print(f"   Via       : RSSHub (works from GitHub servers)")
    print(f"   Market    : Amazon India + Flipkart (₹ only)")
    print(f"   Top Deals : {TOP_DEALS_COUNT} per run — 1 message only")
    print(f"   Channel   : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    all_deals = fetch_telegram_channels()

    print(f"\n📊 Real product deals collected: {len(all_deals)}")

    if not all_deals:
        send_to_telegram(
            "ℹ️ <b>Scan Complete!</b>\n"
            "No deals found this round.\n"
            "🕐 Will check again in 6 hours!"
        )
        return

    # Sort by highest discount first
    all_deals.sort(key=lambda x: x["discount"], reverse=True)

    # Remove duplicates
    seen, unique = set(), []
    for deal in all_deals:
        key = deal["title"][:25].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(deal)

    top5 = unique[:TOP_DEALS_COUNT]

    print(f"\n🏆 Top {len(top5)} deals selected:")
    for i, d in enumerate(top5, 1):
        print(f"   {i}. {d['discount']}% off — {d['title'][:55]}")

    send_top5(top5)


if __name__ == "__main__":
    main()
