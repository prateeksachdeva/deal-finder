import requests
from bs4 import BeautifulSoup
import os
import time
import re

# ============================================================
#   CONFIGURATION — Loaded from GitHub Secrets automatically
# ============================================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
MIN_DISCOUNT        = 60   # Minimum discount % to post
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Avoid posting same deal twice in one run
posted_deals = set()

# Keywords that indicate a heavy deal even without % mentioned
DEAL_KEYWORDS = [
    "loot deal", "loot price", "free", "lowest ever", "lowest price",
    "all time low", "best price ever", "historically low", "massive discount",
    "huge discount", "bumper discount", "flat off", "steal deal"
]


# ────────────────────────────────────────────────────────────
# TELEGRAM — Send message to channel
# ────────────────────────────────────────────────────────────
def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("   ✅ Sent to Telegram!")
            return True
        else:
            print(f"   ❌ Telegram Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Telegram Exception: {e}")
        return False


# ────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────
def extract_discount(text: str) -> int:
    """Extract highest discount % from text"""
    matches = re.findall(r'(\d{1,3})\s*%\s*off', text.lower())
    if matches:
        return max(int(m) for m in matches if int(m) <= 99)
    return 0

def is_deal_keyword(text: str) -> bool:
    """Check if text contains heavy deal keywords"""
    text_lower = text.lower()
    return any(k in text_lower for k in DEAL_KEYWORDS)

def is_indian_platform(text: str) -> bool:
    """Check if deal is from Amazon or Flipkart"""
    text_lower = text.lower()
    return "amazon" in text_lower or "flipkart" in text_lower or "amazon.in" in text_lower

def get_platform(text: str) -> str:
    text_lower = text.lower()
    if "flipkart" in text_lower:
        return "Flipkart"
    if "amazon" in text_lower:
        return "Amazon India"
    return "Online Store"

def already_posted(key: str) -> bool:
    if key in posted_deals:
        return True
    posted_deals.add(key)
    return False


# ────────────────────────────────────────────────────────────
# SOURCE 1 — Smartprix RSS (Fixed — smarter filtering)
# Found 30 items last time! Now we extract deals properly
# ────────────────────────────────────────────────────────────
def scrape_smartprix():
    print("\n🔍 Scanning Smartprix...")
    found = 0

    try:
        response = requests.get(
            "https://www.smartprix.com/feed",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml"},
            timeout=15
        )
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title   = item.find("title").get_text(strip=True)       if item.find("title")       else ""
                link    = item.find("link").get_text(strip=True)         if item.find("link")        else ""
                desc    = item.find("description").get_text(strip=True)  if item.find("description") else ""
                combined = title + " " + desc

                discount = extract_discount(combined)
                is_loot  = is_deal_keyword(combined)

                # Accept if 60%+ discount OR strong deal keywords found
                if discount < MIN_DISCOUNT and not is_loot:
                    continue

                if already_posted(title[:40]):
                    continue

                platform     = get_platform(combined)
                emoji        = "🔥" if discount >= 70 else "💥"
                discount_txt = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>🔥 Heavy Discount!</b>"

                message = (
                    f"{emoji} <b>DEAL — Smartprix</b>\n\n"
                    f"📦 <b>{title}</b>\n\n"
                    f"📉 {discount_txt}\n"
                    f"🏪 Platform: {platform}\n\n"
                    f"🛒 <a href='{link}'>Check Deal →</a>"
                )
                send_to_telegram(message)
                found += 1
                time.sleep(2)

            except Exception:
                continue

    except Exception as e:
        print(f"   ❌ Smartprix error: {e}")

    print(f"   ✅ Smartprix done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# SOURCE 2 — Slickdeals RSS (Global, always works!)
# Huge deal community, many India Amazon deals posted here
# ────────────────────────────────────────────────────────────
def scrape_slickdeals():
    print("\n🔍 Scanning Slickdeals...")
    found = 0

    rss_urls = [
        "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
        "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1&q=amazon",
    ]

    for rss_url in rss_urls:
        try:
            response = requests.get(
                rss_url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml"},
                timeout=15
            )
            soup = BeautifulSoup(response.text, "xml")
            items = soup.find_all("item")
            print(f"   Found {len(items)} deals")

            for item in items:
                try:
                    title   = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                    link    = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                    desc    = item.find("description").get_text(strip=True) if item.find("description") else ""
                    combined = title + " " + desc

                    discount = extract_discount(combined)
                    is_loot  = is_deal_keyword(combined)

                    if discount < MIN_DISCOUNT and not is_loot:
                        continue

                    if already_posted(title[:40]):
                        continue

                    emoji        = "🔥" if discount >= 70 else "💥"
                    discount_txt = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>Heavy Discount!</b>"

                    message = (
                        f"{emoji} <b>DEAL — Slickdeals</b>\n\n"
                        f"📦 <b>{title}</b>\n\n"
                        f"📉 {discount_txt}\n\n"
                        f"🛒 <a href='{link}'>Grab Deal →</a>"
                    )
                    send_to_telegram(message)
                    found += 1
                    time.sleep(2)

                except Exception:
                    continue

        except Exception as e:
            print(f"   ❌ Slickdeals error: {e}")

    print(f"   ✅ Slickdeals done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# SOURCE 3 — Cashkaro Blog RSS
# Indian cashback site — posts Amazon & Flipkart deals daily
# ────────────────────────────────────────────────────────────
def scrape_cashkaro():
    print("\n🔍 Scanning Cashkaro deals...")
    found = 0

    try:
        response = requests.get(
            "https://cashkaro.com/blog/feed",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml"},
            timeout=15
        )
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title   = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link    = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc    = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc

                discount = extract_discount(combined)
                is_loot  = is_deal_keyword(combined)

                if discount < MIN_DISCOUNT and not is_loot:
                    continue

                if already_posted(title[:40]):
                    continue

                platform     = get_platform(combined)
                emoji        = "🔥" if discount >= 70 else "💰"
                discount_txt = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>Big Savings!</b>"

                message = (
                    f"{emoji} <b>DEAL — Cashkaro</b>\n\n"
                    f"📦 <b>{title}</b>\n\n"
                    f"📉 {discount_txt}\n"
                    f"🏪 Platform: {platform}\n\n"
                    f"🛒 <a href='{link}'>Shop Now →</a>"
                )
                send_to_telegram(message)
                found += 1
                time.sleep(2)

            except Exception:
                continue

    except Exception as e:
        print(f"   ❌ Cashkaro error: {e}")

    print(f"   ✅ Cashkaro done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# SOURCE 4 — GizChina / 91mobiles RSS
# Tech deals — mobiles, electronics, gadgets
# ────────────────────────────────────────────────────────────
def scrape_91mobiles():
    print("\n🔍 Scanning 91mobiles deals...")
    found = 0

    try:
        response = requests.get(
            "https://www.91mobiles.com/hub/feed/",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml"},
            timeout=15
        )
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items")

        for item in items:
            try:
                title   = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link    = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc    = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc

                # Only deal/offer articles
                deal_indicators = ["deal", "offer", "discount", "sale", "off", "price drop", "price cut"]
                if not any(d in combined.lower() for d in deal_indicators):
                    continue

                discount = extract_discount(combined)
                is_loot  = is_deal_keyword(combined)

                if discount < MIN_DISCOUNT and not is_loot:
                    continue

                if already_posted(title[:40]):
                    continue

                platform     = get_platform(combined)
                discount_txt = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>Great Deal!</b>"

                message = (
                    f"📱 <b>TECH DEAL — 91mobiles</b>\n\n"
                    f"📦 <b>{title}</b>\n\n"
                    f"📉 {discount_txt}\n"
                    f"🏪 Platform: {platform}\n\n"
                    f"🛒 <a href='{link}'>See Deal →</a>"
                )
                send_to_telegram(message)
                found += 1
                time.sleep(2)

            except Exception:
                continue

    except Exception as e:
        print(f"   ❌ 91mobiles error: {e}")

    print(f"   ✅ 91mobiles done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*50)
    print("🚀 Deal Finder Bot Started!")
    print(f"   Minimum Discount : {MIN_DISCOUNT}%")
    print(f"   Posting to       : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    send_to_telegram(
        "🤖 <b>Deal Bot Scanning...</b>\n"
        "📡 Sources: Smartprix | Slickdeals | Cashkaro | 91mobiles\n"
        "🎯 Filter: 60%+ OFF deals only!"
    )

    total  = 0
    total += scrape_smartprix()
    total += scrape_slickdeals()
    total += scrape_cashkaro()
    total += scrape_91mobiles()

    print(f"\n{'='*50}")
    print(f"✅ Done! {total} deals posted to Telegram.")
    print(f"{'='*50}")

    if total == 0:
        send_to_telegram(
            "ℹ️ <b>Scan Complete!</b>\n"
            "No new deals above 60% found this round.\n"
            "🕐 Will check again in 6 hours!"
        )
    else:
        send_to_telegram(
            f"✅ <b>Scan Complete!</b>\n"
            f"Posted <b>{total} deals</b> above 60% off!\n"
            f"🕐 Next scan in 6 hours!"
        )


if __name__ == "__main__":
    main()
