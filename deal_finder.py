import requests
from bs4 import BeautifulSoup
import os
import re

# ============================================================
#   CONFIGURATION
# ============================================================
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
TOP_DEALS_COUNT     = 5
# ============================================================

# ────────────────────────────────────────────────────────────
# BLOG ARTICLE FILTERS — Skip these, they are NOT real deals
# ────────────────────────────────────────────────────────────
BLOG_PATTERNS = [
    r'^top\s+\d+',           # "Top 15 deals..."
    r'^best\s+\d+',          # "Best 10 products..."
    r'biggest sales',
    r'you can\'t miss',
    r'shop smarter',
    r'step into style',
    r'light up your',
    r'how to',
    r'guide to',
    r'tips for',
    r'ways to',
    r'things you',
    r'reasons why',
    r'everything you',
    r'all you need',
    r'what is',
    r'why you should',
    r'festival.*deals',      # "Diwali deals guide"
    r'sale.*\d{4}',          # "Big Billion Days 2025"
    r'\d+ deals',            # "15 deals you..."
    r'\d+ things',
    r'\d+ best',
    r'\d+ ways',
]

def is_blog_article(title: str) -> bool:
    t = title.lower().strip()
    return any(re.search(p, t) for p in BLOG_PATTERNS)

# ────────────────────────────────────────────────────────────
# REAL DEAL INDICATORS — Must have at least one of these
# ────────────────────────────────────────────────────────────
def is_real_product_deal(title: str, desc: str) -> bool:
    combined = (title + " " + desc).lower()
    # Must mention price or discount
    has_price    = bool(re.search(r'₹|rs\.|inr|rupee', combined))
    has_discount = bool(re.search(r'\d+\s*%\s*off|discount|deal price|loot', combined))
    has_platform = "amazon" in combined or "flipkart" in combined
    return (has_price or has_discount) and has_platform

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
# DESIDIME — India's Biggest Real Deal Community
# People post actual products with MRP, deal price, % off
# Example: "boAt Airdopes 141 at ₹999 (MRP ₹4499) 78% off Amazon"
# ────────────────────────────────────────────────────────────
def fetch_desidime() -> list:
    print("\n🔍 Fetching Desidime real product deals...")
    deals = []

    feeds = [
        ("All Deals",      "https://www.desidime.com/deals.rss"),
        ("Electronics",    "https://www.desidime.com/selective_search/electronics.rss"),
        ("Mobiles",        "https://www.desidime.com/selective_search/mobiles.rss"),
        ("Fashion",        "https://www.desidime.com/selective_search/fashion.rss"),
        ("Home Kitchen",   "https://www.desidime.com/selective_search/home-kitchen.rss"),
        ("Freebies",       "https://www.desidime.com/selective_search/freebies.rss"),
        ("Grocery",        "https://www.desidime.com/selective_search/grocery.rss"),
        ("Sports",         "https://www.desidime.com/selective_search/sports-fitness.rss"),
    ]

    for name, url in feeds:
        try:
            r    = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            soup = BeautifulSoup(r.text, "xml")
            items = soup.find_all("item")
            print(f"   [{name}] → {len(items)} items")

            for item in items:
                try:
                    title = item.find("title").get_text(strip=True)      if item.find("title")       else ""
                    link  = item.find("link").get_text(strip=True)        if item.find("link")        else ""
                    desc  = item.find("description").get_text(strip=True) if item.find("description") else ""
                    combined = title + " " + desc

                    # ✅ STRICT FILTERS — Skip blog articles
                    if is_blog_article(title):
                        continue

                    # ✅ Must be a real product deal
                    if not is_real_product_deal(title, desc):
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
                        "source"        : f"Desidime/{name}"
                    })

                except:
                    continue

        except Exception as e:
            print(f"   ❌ {name} error: {e}")

    print(f"\n   ✅ Total real deals from Desidime: {len(deals)}")
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
    print("🚀 India Deal Finder — Real Products Only!")
    print(f"   Source    : Desidime (Real community deals)")
    print(f"   Market    : Amazon India + Flipkart (₹ only)")
    print(f"   Filter    : Blog articles removed automatically")
    print(f"   Top Deals : {TOP_DEALS_COUNT} per run — 1 Telegram message")
    print(f"   Channel   : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    all_deals = fetch_desidime()

    print(f"\n📊 Real product deals collected: {len(all_deals)}")

    if not all_deals:
        send_to_telegram(
            "ℹ️ <b>Scan Complete!</b>\n"
            "No product deals found this round.\n"
            "🕐 Will check again in 6 hours!"
        )
        return

    # Sort by highest discount first
    all_deals.sort(key=lambda x: x["discount"], reverse=True)

    # Remove duplicate titles
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
