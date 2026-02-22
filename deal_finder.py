import requests
from bs4 import BeautifulSoup
import os
import re
import time

# ============================================================
#   CONFIGURATION — Loaded from GitHub Secrets automatically
# ============================================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
MIN_DISCOUNT        = 60   # Minimum discount %
TOP_DEALS_COUNT     = 5    # Only post top 5 deals per run
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


# ────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────
def extract_discount(text: str) -> int:
    """Extract highest discount % from text"""
    matches = re.findall(r'(\d{1,3})\s*%\s*off', text.lower())
    if matches:
        return max(int(m) for m in matches if int(m) <= 95)
    return 0

def extract_price_inr(text: str) -> list:
    """Extract ₹ prices from text"""
    prices = []
    for pattern in [r'₹\s*([\d,]+)', r'Rs\.?\s*([\d,]+)', r'INR\s*([\d,]+)']:
        for m in re.findall(pattern, text):
            try:
                prices.append(int(m.replace(",", "")))
            except:
                pass
    return sorted(prices)

def is_india_deal(text: str) -> bool:
    """Only Amazon.in or Flipkart deals"""
    t = text.lower()
    return "amazon.in" in t or "amazon india" in t or "flipkart" in t or "amazon" in t

def get_platform(text: str) -> str:
    t = text.lower()
    if "flipkart" in t:
        return "Flipkart"
    return "Amazon India"


# ────────────────────────────────────────────────────────────
# TELEGRAM — Send ONE message with all top 5 deals
# ────────────────────────────────────────────────────────────
def send_top5_to_telegram(deals: list):
    """Send all top 5 deals in a single nicely formatted message"""

    message = "🇮🇳 <b>TOP 5 DEALS TODAY — India</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, deal in enumerate(deals, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔥"
        message += f"{emoji} <b>#{i} — {deal['platform']}</b>\n"
        message += f"📦 {deal['title']}\n"

        if deal['original_price'] and deal['deal_price']:
            message += f"🏷️ MRP: <s>₹{deal['original_price']:,}</s>\n"
            message += f"💰 Price: <b>₹{deal['deal_price']:,}</b>\n"

        message += f"📉 Discount: <b>{deal['discount']}% OFF</b>\n"
        message += f"🛒 <a href='{deal['link']}'>Buy Now →</a>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += "⏰ <i>Next scan in 6 hours!</i>"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Top 5 deals sent to Telegram!")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def send_simple(message: str):
    """Send a simple notification message"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    }, timeout=10)


# ────────────────────────────────────────────────────────────
# SOURCE 1 — Cashkaro India RSS
# India's biggest cashback site — Amazon.in + Flipkart deals
# ────────────────────────────────────────────────────────────
def fetch_cashkaro() -> list:
    print("\n🔍 Fetching Cashkaro deals...")
    deals = []
    try:
        response = requests.get(
            "https://cashkaro.com/blog/feed",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        soup  = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} articles")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)       if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)         if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True)  if item.find("description") else ""
                combined = title + " " + desc

                if not is_india_deal(combined):
                    continue

                discount = extract_discount(combined)
                if discount < MIN_DISCOUNT:
                    continue

                prices        = extract_price_inr(combined)
                deal_price    = prices[0]  if len(prices) >= 1 else None
                original_price = prices[-1] if len(prices) >= 2 else None

                deals.append({
                    "title"         : title[:80],
                    "link"          : link,
                    "discount"      : discount,
                    "deal_price"    : deal_price,
                    "original_price": original_price,
                    "platform"      : get_platform(combined),
                    "source"        : "Cashkaro"
                })
            except:
                continue

    except Exception as e:
        print(f"   ❌ Cashkaro error: {e}")

    print(f"   ✅ Cashkaro — {len(deals)} qualifying deals found")
    return deals


# ────────────────────────────────────────────────────────────
# SOURCE 2 — Smartprix RSS
# Tracks Amazon.in + Flipkart price drops in ₹
# ────────────────────────────────────────────────────────────
def fetch_smartprix() -> list:
    print("\n🔍 Fetching Smartprix deals...")
    deals = []
    try:
        response = requests.get(
            "https://www.smartprix.com/feed",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        soup  = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)       if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)         if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True)  if item.find("description") else ""
                combined = title + " " + desc

                discount = extract_discount(combined)
                if discount < MIN_DISCOUNT:
                    continue

                prices         = extract_price_inr(combined)
                deal_price     = prices[0]   if len(prices) >= 1 else None
                original_price = prices[-1]  if len(prices) >= 2 else None

                # Only include if prices are in ₹ (Indian market)
                if not prices and not is_india_deal(combined):
                    continue

                deals.append({
                    "title"         : title[:80],
                    "link"          : link,
                    "discount"      : discount,
                    "deal_price"    : deal_price,
                    "original_price": original_price,
                    "platform"      : get_platform(combined),
                    "source"        : "Smartprix"
                })
            except:
                continue

    except Exception as e:
        print(f"   ❌ Smartprix error: {e}")

    print(f"   ✅ Smartprix — {len(deals)} qualifying deals found")
    return deals


# ────────────────────────────────────────────────────────────
# SOURCE 3 — 91mobiles RSS
# Indian tech site — posts Amazon.in + Flipkart deals in ₹
# ────────────────────────────────────────────────────────────
def fetch_91mobiles() -> list:
    print("\n🔍 Fetching 91mobiles deals...")
    deals = []
    try:
        response = requests.get(
            "https://www.91mobiles.com/hub/feed/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        soup  = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)       if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)         if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True)  if item.find("description") else ""
                combined = title + " " + desc

                # Only deal/offer articles
                if not any(d in combined.lower() for d in ["deal", "offer", "discount", "off", "sale"]):
                    continue

                discount = extract_discount(combined)
                if discount < MIN_DISCOUNT:
                    continue

                prices         = extract_price_inr(combined)
                deal_price     = prices[0]  if len(prices) >= 1 else None
                original_price = prices[-1] if len(prices) >= 2 else None

                deals.append({
                    "title"         : title[:80],
                    "link"          : link,
                    "discount"      : discount,
                    "deal_price"    : deal_price,
                    "original_price": original_price,
                    "platform"      : get_platform(combined),
                    "source"        : "91mobiles"
                })
            except:
                continue

    except Exception as e:
        print(f"   ❌ 91mobiles error: {e}")

    print(f"   ✅ 91mobiles — {len(deals)} qualifying deals found")
    return deals


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*50)
    print("🚀 India Deal Finder Started!")
    print(f"   Market          : India Only (₹)")
    print(f"   Min Discount    : {MIN_DISCOUNT}%")
    print(f"   Top Deals       : {TOP_DEALS_COUNT} per run")
    print(f"   Posting to      : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    # Collect all deals from all sources
    all_deals = []
    all_deals += fetch_cashkaro()
    all_deals += fetch_smartprix()
    all_deals += fetch_91mobiles()

    print(f"\n📊 Total deals found across all sources: {len(all_deals)}")

    if not all_deals:
        send_simple(
            "ℹ️ <b>Scan Complete!</b>\n"
            "No deals above 60% found this round.\n"
            "🕐 Will check again in 6 hours!"
        )
        return

    # Sort by discount % — highest first
    all_deals.sort(key=lambda x: x["discount"], reverse=True)

    # Remove duplicates by title
    seen   = set()
    unique = []
    for deal in all_deals:
        key = deal["title"][:30].lower()
        if key not in seen:
            seen.add(key)
            unique.append(deal)

    # Pick only top 5
    top5 = unique[:TOP_DEALS_COUNT]

    print(f"\n🏆 Top {len(top5)} deals selected:")
    for i, d in enumerate(top5, 1):
        print(f"   {i}. {d['discount']}% off — {d['title'][:50]} [{d['source']}]")

    # Send as ONE message to Telegram
    send_top5_to_telegram(top5)


if __name__ == "__main__":
    main()
