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
    "Accept": "application/json",
}

# Avoid posting same deal twice
posted_deals = set()


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
        else:
            print(f"   ❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Telegram Exception: {e}")


# ────────────────────────────────────────────────────────────
# HELPER — Extract discount % from text
# ────────────────────────────────────────────────────────────
def extract_discount(text: str) -> int:
    matches = re.findall(r'(\d{1,3})\s*%\s*off', text.lower())
    if matches:
        return max(int(m) for m in matches)
    return 0


# ────────────────────────────────────────────────────────────
# SOURCE 1 — Reddit r/IndianDeals
# Works globally, thousands of Amazon/Flipkart deals daily
# ────────────────────────────────────────────────────────────
def scrape_reddit_indian_deals():
    print("\n🔍 Scanning Reddit r/IndianDeals...")
    found = 0

    subreddits = [
        "https://www.reddit.com/r/IndianDeals.json?limit=50&sort=new",
        "https://www.reddit.com/r/indiashopping.json?limit=50&sort=new",
    ]

    for url in subreddits:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            data = response.json()
            posts = data["data"]["children"]
            print(f"   Found {len(posts)} posts")

            for post in posts:
                try:
                    p        = post["data"]
                    title    = p.get("title", "")
                    link     = p.get("url", "")
                    text     = p.get("selftext", "")
                    score    = p.get("score", 0)
                    combined = title + " " + text

                    # Only Amazon or Flipkart deals
                    is_amazon   = "amazon" in combined.lower()
                    is_flipkart = "flipkart" in combined.lower()
                    if not is_amazon and not is_flipkart:
                        continue

                    platform = "Amazon India" if is_amazon else "Flipkart"
                    discount = extract_discount(combined)

                    loot_keywords = ["loot deal", "free", "lowest price", "all time low"]
                    is_loot = any(k in combined.lower() for k in loot_keywords)

                    if discount < MIN_DISCOUNT and not is_loot:
                        continue

                    deal_key = title[:40]
                    if deal_key in posted_deals:
                        continue
                    posted_deals.add(deal_key)

                    emoji = "🔥" if discount >= 70 else "💥"
                    discount_text = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>Heavy Discount!</b>"

                    message = (
                        f"{emoji} <b>DEAL ALERT — {platform}</b>\n\n"
                        f"📦 <b>{title}</b>\n\n"
                        f"📉 Discount: {discount_text}\n"
                        f"👍 Upvotes: {score}\n\n"
                        f"🛒 <a href='{link}'>Buy Now →</a>\n"
                        f"💬 <a href='https://reddit.com{p.get('permalink', '')}'>Discussion →</a>"
                    )

                    send_to_telegram(message)
                    found += 1
                    time.sleep(2)

                except Exception:
                    continue

        except Exception as e:
            print(f"   ❌ Reddit error: {e}")

    print(f"   ✅ Reddit done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# SOURCE 2 — DesiDime RSS
# ────────────────────────────────────────────────────────────
def scrape_desidime():
    print("\n🔍 Scanning DesiDime deals...")
    found = 0

    rss_urls = [
        "https://www.desidime.com/deals.rss",
        "https://www.desidime.com/selective_search/freebies.rss",
    ]

    for rss_url in rss_urls:
        try:
            response = requests.get(rss_url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/rss+xml"
            }, timeout=15)

            soup = BeautifulSoup(response.text, "xml")
            items = soup.find_all("item")
            print(f"   Found {len(items)} deals on DesiDime")

            for item in items:
                try:
                    title    = item.find("title").get_text(strip=True)       if item.find("title")       else ""
                    link     = item.find("link").get_text(strip=True)         if item.find("link")         else ""
                    desc     = item.find("description").get_text(strip=True)  if item.find("description")  else ""
                    combined = title + " " + desc
                    discount = extract_discount(combined)

                    loot_keywords = ["loot", "free", "lowest ever", "all time low"]
                    is_loot = any(k in combined.lower() for k in loot_keywords)

                    if discount < MIN_DISCOUNT and not is_loot:
                        continue

                    deal_key = title[:40]
                    if deal_key in posted_deals:
                        continue
                    posted_deals.add(deal_key)

                    discount_text = f"<b>{discount}% OFF</b>" if discount > 0 else "<b>🔥 Loot Deal!</b>"

                    message = (
                        f"🎯 <b>HOT DEAL — DesiDime</b>\n\n"
                        f"📦 <b>{title}</b>\n\n"
                        f"📉 {discount_text}\n\n"
                        f"🛒 <a href='{link}'>Grab Now →</a>"
                    )

                    send_to_telegram(message)
                    found += 1
                    time.sleep(2)

                except Exception:
                    continue

        except Exception as e:
            print(f"   ❌ DesiDime error: {e}")

    print(f"   ✅ DesiDime done — {found} deals posted")
    return found


# ────────────────────────────────────────────────────────────
# SOURCE 3 — Smartprix RSS
# ────────────────────────────────────────────────────────────
def scrape_smartprix():
    print("\n🔍 Scanning Smartprix price drops...")
    found = 0

    try:
        response = requests.get("https://www.smartprix.com/feed", headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/rss+xml, application/xml"
        }, timeout=15)

        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")
        print(f"   Found {len(items)} items on Smartprix")

        for item in items:
            try:
                title    = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                link     = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                desc     = item.find("description").get_text(strip=True) if item.find("description") else ""
                combined = title + " " + desc
                discount = extract_discount(combined)

                if discount < MIN_DISCOUNT:
                    continue

                deal_key = title[:40]
                if deal_key in posted_deals:
                    continue
                posted_deals.add(deal_key)

                message = (
                    f"💰 <b>PRICE DROP — Smartprix</b>\n\n"
                    f"📦 <b>{title}</b>\n\n"
                    f"📉 Discount: <b>{discount}% OFF</b>\n\n"
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
# MAIN
# ────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*50)
    print("🚀 Deal Finder Bot Started!")
    print(f"   Minimum Discount : {MIN_DISCOUNT}%")
    print(f"   Posting to       : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    send_to_telegram(
        "🤖 <b>Deal Bot Started!</b>\n"
        "Scanning Reddit, DesiDime & Smartprix for 60%+ deals..."
    )

    total  = 0
    total += scrape_reddit_indian_deals()
    total += scrape_desidime()
    total += scrape_smartprix()

    print(f"\n{'='*50}")
    print(f"✅ Done! {total} deals posted to Telegram.")
    print(f"{'='*50}")

    if total == 0:
        send_to_telegram(
            "ℹ️ <b>Scan complete!</b>\n"
            "No new deals above 60% found this round.\n"
            "Will check again in 6 hours! 🕐"
        )


if __name__ == "__main__":
    main()
