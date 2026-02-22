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

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────
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
                if 10 < val < 10000000:  # Filter out junk numbers
                    prices.append(val)
            except:
                pass
    return sorted(set(prices))

def get_platform(text: str) -> str:
    t = text.lower()
    if "flipkart" in t:
        return "Flipkart"
    return "Amazon India"

def is_deal_article(text: str) -> bool:
    deal_words = ["deal", "offer", "discount", "% off", "sale", "price drop", "loot", "buy"]
    return any(w in text.lower() for w in deal_words)

def calculate_discount(deal_price, original_price) -> int:
    if deal_price and original_price and original_price > deal_price:
        return int(((original_price - deal_price) / original_price) * 100)
    return 0

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
# SOURCE 1 — Desidime RSS (Best India Deal Source!)
# Real Amazon.in + Flipkart deals posted by Indian users
# With actual product names, MRP and deal prices in ₹
# ────────────────────────────────────────────────────────────
def fetch_desidime() -> list:
    print("\n🔍 Fetching Desidime deals...")
    deals = []

    # Multiple category RSS feeds from Desidime
    rss_feeds = [
        "https://www.desidime.com/deals.rss",                          # All deals
        "https://www.desidime.com/selective_search/electronics.rss",    # Electronics
        "https://www.desidime.com/selective_search/mobiles.rss",        # Mobiles
        "https://www.desidime.com/selective_search/fashion.rss",        # Fashion
        "https://www.desidime.com/selective_search/home-kitchen.rss",   # Home & Kitchen
        "https://www.desidime.com/selective_search/freebies.rss",       # Freebies/Loot
    ]

    for feed_url in rss_feeds:
        try:
            r    = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item")
            print(f"   {feed_url.split('/')[-1]} → {len(items)} items")

            for item in items:
                try:
                    title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                    link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                    desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                    combined = title + " " + desc

                    discount = extract_discount(combined)
                    prices   = extract_prices_inr(combined)

                    deal_price     = prices[0]  if len(prices) >= 1 else None
                    original_price = prices[-1] if len(prices) >= 2 else None

                    # Calculate discount from prices if not mentioned explicitly
                    if discount == 0 and deal_price and original_price:
                        discount = calculate_discount(deal_price, original_price)

                    deals.append({
                        "title"         : title[:80],
                        "link"          : link,
                        "discount"      : discount,
                        "deal_price"    : deal_price,
                        "original_price": original_price,
                        "platform"      : get_platform(combined),
                        "source"        : "Desidime"
                    })
                except:
                    continue

        except Exception as e:
            print(f"   ❌ Error {feed_url}: {e}")

    print(f"   ✅ Desidime total — {len(deals)} deals collected")
    return deals


# ────────────────────────────────────────────────────────────
# SOURCE 2 — Coupondunia India
# Real Amazon.in + Flipkart product deals with prices in ₹
# ────────────────────────────────────────────────────────────
def fetch_coupondunia() -> list:
    print("\n🔍 Fetching Coupondunia deals...")
    deals = []
    try:
        r    = requests.get("https://coupondunia.in/blog/feed/",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc

                # Skip if not a deal article
                if not is_deal_article(combined):
                    continue

                discount = extract_discount(combined)
                prices   = extract_prices_inr(combined)

                deal_price     = prices[0]  if len(prices) >= 1 else None
                original_price = prices[-1] if len(prices) >= 2 else None

                if discount == 0 and deal_price and original_price:
                    discount = calculate_discount(deal_price, original_price)

                deals.append({
                    "title"         : title[:80],
                    "link"          : link,
                    "discount"      : discount,
                    "deal_price"    : deal_price,
                    "original_price": original_price,
                    "platform"      : get_platform(combined),
                    "source"        : "Coupondunia"
                })
            except:
                continue

    except Exception as e:
        print(f"   ❌ Coupondunia error: {e}")

    print(f"   ✅ Coupondunia — {len(deals)} deals collected")
    return deals


# ────────────────────────────────────────────────────────────
# SOURCE 3 — GrabOn India
# Amazon.in + Flipkart deals, coupons, offers in ₹
# ────────────────────────────────────────────────────────────
def fetch_grabon() -> list:
    print("\n🔍 Fetching GrabOn deals...")
    deals = []
    try:
        r    = requests.get("https://www.grabon.in/indias-best-deals/feed/",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc

                if not is_deal_article(combined):
                    continue

                discount = extract_discount(combined)
                prices   = extract_prices_inr(combined)

                deal_price     = prices[0]  if len(prices) >= 1 else None
                original_price = prices[-1] if len(prices) >= 2 else None

                if discount == 0 and deal_price and original_price:
                    discount = calculate_discount(deal_price, original_price)

                deals.append({
                    "title"         : title[:80],
                    "link"          : link,
                    "discount"      : discount,
                    "deal_price"    : deal_price,
                    "original_price": original_price,
                    "platform"      : get_platform(combined),
                    "source"        : "GrabOn"
                })
            except:
                continue

    except Exception as e:
        print(f"   ❌ GrabOn error: {e}")

    print(f"   ✅ GrabOn — {len(deals)} deals collected")
    return deals


# ────────────────────────────────────────────────────────────
# SOURCE 4 — 91mobiles Deals RSS
# Only deal articles — mobiles + electronics on Amazon/Flipkart
# ────────────────────────────────────────────────────────────
def fetch_91mobiles() -> list:
    print("\n🔍 Fetching 91mobiles deals...")
    deals = []
    try:
        r    = requests.get("https://www.91mobiles.com/hub/deals/feed/",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc

                discount = extract_discount(combined)
                prices   = extract_prices_inr(combined)

                deal_price     = prices[0]  if len(prices) >= 1 else None
                original_price = prices[-1] if len(prices) >= 2 else None

                if discount == 0 and deal_price and original_price:
                    discount = calculate_discount(deal_price, original_price)

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

    print(f"   ✅ 91mobiles — {len(deals)} deals collected")
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
        message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += "⏰ <i>Next scan in 6 hours!</i>"
    send_to_telegram(message)


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*50)
    print("🚀 India Deal Finder Started!")
    print(f"   Market    : Amazon India + Flipkart (₹ only)")
    print(f"   Top Deals : Top {TOP_DEALS_COUNT} per run — 1 message only")
    print(f"   Channel   : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    # Collect from all proper India deal sources
    all_deals = []
    all_deals += fetch_desidime()    # Best source — real community deals
    all_deals += fetch_91mobiles()   # Tech deals
    all_deals += fetch_coupondunia() # India deals site
    all_deals += fetch_grabon()      # India deals site

    print(f"\n📊 Total deals collected from all sources: {len(all_deals)}")

    if not all_deals:
        send_to_telegram(
            "ℹ️ <b>Scan Complete!</b>\n"
            "No deals found this round.\n"
            "🕐 Will check again in 6 hours!"
        )
        return

    # Sort by highest discount first
    all_deals.sort(key=lambda x: x["discount"], reverse=True)

    # Remove duplicates by title
    seen, unique = set(), []
    for deal in all_deals:
        key = deal["title"][:25].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(deal)

    # Pick top 5
    top5 = unique[:TOP_DEALS_COUNT]

    print(f"\n🏆 Top {len(top5)} deals selected:")
    for i, d in enumerate(top5, 1):
        print(f"   {i}. {d['discount']}% off — {d['title'][:50]} [{d['source']}]")

    send_top5(top5)


if __name__ == "__main__":
    main()
