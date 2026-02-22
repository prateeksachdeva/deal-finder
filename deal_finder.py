import requests
from bs4 import BeautifulSoup
import time

# ============================================================
#   CONFIGURATION — Fill these before running
# ============================================================
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"       # From @BotFather
TELEGRAM_CHANNEL_ID = "@YourChannelName"    # Your channel e.g. @mydeals
MIN_DISCOUNT_PERCENT = 60                   # Minimum 60% discount
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

# Track already posted deals (avoid duplicate posts)
posted_deals = set()


# ────────────────────────────────────────────────────────────
# TELEGRAM — Send deal message to your channel
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
            print("✅ Deal sent to Telegram!")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")


def format_deal_message(name, original_price, deal_price, discount, link, platform):
    return (
        f"🔥 <b>DEAL ALERT — {platform}</b>\n\n"
        f"📦 <b>{name}</b>\n\n"
        f"🏷️ Original Price: <s>₹{original_price:,}</s>\n"
        f"💰 Deal Price: <b>₹{deal_price:,}</b>\n"
        f"📉 Discount: <b>{discount}% OFF</b>\n\n"
        f"🛒 <a href='{link}'>Buy Now →</a>"
    )


# ────────────────────────────────────────────────────────────
# AMAZON — Scrape Today's Deals page
# ────────────────────────────────────────────────────────────
def scrape_amazon():
    print("\n🔍 Scanning Amazon India deals...")
    found = 0

    urls = [
        "https://www.amazon.in/deals",
        "https://www.amazon.in/gp/goldbox",
    ]

    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all deal cards on the page
            deal_cards = soup.find_all("div", {"data-testid": "deal-card"})
            if not deal_cards:
                deal_cards = soup.find_all("div", class_=lambda c: c and "DealCard" in c)
            if not deal_cards:
                deal_cards = soup.find_all("div", attrs={"data-component-type": "s-search-result"})

            print(f"   Found {len(deal_cards)} products on Amazon page")

            for card in deal_cards:
                try:
                    # Product name
                    name_tag = (
                        card.find("span", {"data-testid": "deal-title"}) or
                        card.find("span", class_=lambda c: c and "title" in str(c).lower()) or
                        card.find("h2")
                    )
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)

                    # Discount percentage
                    discount_tag = (
                        card.find("span", {"data-testid": "deal-badge"}) or
                        card.find("span", class_=lambda c: c and "percent" in str(c).lower())
                    )
                    if not discount_tag:
                        continue
                    discount_text = discount_tag.get_text(strip=True)
                    discount = int(''.join(filter(str.isdigit, discount_text.split('%')[0][-3:])))

                    if discount < MIN_DISCOUNT_PERCENT:
                        continue

                    # Prices
                    prices = card.find_all("span", class_=lambda c: c and "price" in str(c).lower())
                    deal_price = None
                    original_price = None
                    for p in prices:
                        text = p.get_text(strip=True).replace("₹", "").replace(",", "").strip()
                        if text.isdigit():
                            val = int(text)
                            if deal_price is None:
                                deal_price = val
                            elif val > deal_price:
                                original_price = val
                                break

                    if not deal_price or not original_price:
                        continue

                    # Product link
                    link_tag = card.find("a", href=True)
                    link = "https://www.amazon.in" + link_tag["href"] if link_tag and link_tag["href"].startswith("/") else (link_tag["href"] if link_tag else url)

                    # Avoid duplicates
                    deal_key = f"amazon_{name[:30]}"
                    if deal_key in posted_deals:
                        continue
                    posted_deals.add(deal_key)

                    message = format_deal_message(name, original_price, deal_price, discount, link, "Amazon India")
                    send_to_telegram(message)
                    found += 1
                    time.sleep(1)

                except Exception:
                    continue

        except Exception as e:
            print(f"❌ Amazon scrape error: {e}")

    print(f"✅ Amazon done — {found} deals found above {MIN_DISCOUNT_PERCENT}%")


# ────────────────────────────────────────────────────────────
# FLIPKART — Scrape Deals of the Day
# ────────────────────────────────────────────────────────────
def scrape_flipkart():
    print("\n🔍 Scanning Flipkart deals...")
    found = 0

    urls = [
        "https://www.flipkart.com/offers-list/deals-of-the-day",
        "https://www.flipkart.com/offers-list/mobiles-deals",
        "https://www.flipkart.com/offers-list/electronics-deals",
    ]

    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")

            products = soup.find_all("div", class_=lambda c: c and c in ["_1AtVbE", "_4ddWXP", "CXW8mj"])
            if not products:
                products = soup.find_all("div", class_="_13oc-S")

            print(f"   Found {len(products)} products on Flipkart page")

            for product in products:
                try:
                    name_tag = (
                        product.find("div", class_="_4rR01T") or
                        product.find("a", class_="s1Q9rs") or
                        product.find("div", class_="KzDlHZ")
                    )
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)

                    discount_tag = (
                        product.find("div", class_="_3Ay6Sb") or
                        product.find("span", class_="_1_WHN1") or
                        product.find("div", class_="UkUFwK")
                    )
                    if not discount_tag:
                        continue
                    discount_text = discount_tag.get_text(strip=True)
                    discount = int(''.join(filter(str.isdigit, discount_text.split('%')[0][-3:])))

                    if discount < MIN_DISCOUNT_PERCENT:
                        continue

                    price_tag = product.find("div", class_="_30jeq3") or product.find("div", class_="Nx9bqj")
                    deal_price_text = price_tag.get_text(strip=True).replace("₹", "").replace(",", "") if price_tag else None
                    deal_price = int(deal_price_text) if deal_price_text and deal_price_text.isdigit() else None

                    orig_tag = product.find("div", class_="_3I9_wc") or product.find("div", class_="yRaY8j")
                    orig_text = orig_tag.get_text(strip=True).replace("₹", "").replace(",", "") if orig_tag else None
                    original_price = int(orig_text) if orig_text and orig_text.isdigit() else None

                    if not deal_price or not original_price:
                        continue

                    link_tag = product.find("a", href=True)
                    link = "https://www.flipkart.com" + link_tag["href"] if link_tag else url

                    deal_key = f"flipkart_{name[:30]}"
                    if deal_key in posted_deals:
                        continue
                    posted_deals.add(deal_key)

                    message = format_deal_message(name, original_price, deal_price, discount, link, "Flipkart")
                    send_to_telegram(message)
                    found += 1
                    time.sleep(1)

                except Exception:
                    continue

        except Exception as e:
            print(f"❌ Flipkart scrape error: {e}")

    print(f"✅ Flipkart done — {found} deals found above {MIN_DISCOUNT_PERCENT}%")


# ────────────────────────────────────────────────────────────
# DESIDIME RSS — Extra source, never gets blocked
# ────────────────────────────────────────────────────────────
def scrape_desidime():
    print("\n🔍 Scanning DesiDime hot deals...")
    found = 0

    rss_url = "https://www.desidime.com/deals.rss"

    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")

        print(f"   Found {len(items)} deals on DesiDime")

        for item in items:
            try:
                title = item.find("title").get_text(strip=True)
                link = item.find("link").get_text(strip=True)
                description = item.find("description").get_text(strip=True) if item.find("description") else ""

                # Try to extract discount % from title/description
                discount = 0
                combined = title + " " + description
                if "% off" in combined.lower():
                    parts = combined.lower().split("% off")
                    nums = ''.join(filter(str.isdigit, parts[0][-3:]))
                    discount = int(nums) if nums else 0

                deal_key = f"desidime_{title[:30]}"
                if deal_key in posted_deals:
                    continue
                posted_deals.add(deal_key)

                if discount >= MIN_DISCOUNT_PERCENT or "loot" in title.lower():
                    message = (
                        f"🔥 <b>HOT DEAL — DesiDime</b>\n\n"
                        f"📦 <b>{title}</b>\n\n"
                        f"📉 Discount: <b>{discount}% OFF</b>\n\n"
                        f"🛒 <a href='{link}'>Check Deal →</a>"
                    )
                    send_to_telegram(message)
                    found += 1
                    time.sleep(1)

            except Exception:
                continue

    except Exception as e:
        print(f"❌ DesiDime error: {e}")

    print(f"✅ DesiDime done — {found} deals posted")


# ────────────────────────────────────────────────────────────
# MAIN — Run all scrapers
# ────────────────────────────────────────────────────────────
def run_all():
    print("\n" + "="*50)
    print("🚀 Deal Finder Started!")
    print(f"   Minimum Discount : {MIN_DISCOUNT_PERCENT}%")
    print(f"   Posting to       : {TELEGRAM_CHANNEL_ID}")
    print("="*50)

    send_to_telegram("🤖 <b>Deal Bot is now scanning Amazon, Flipkart & DesiDime for 60%+ deals...</b>")

    scrape_desidime()   # Most reliable — RSS feed, never blocked
    scrape_amazon()
    scrape_flipkart()

    print("\n✅ All done! Waiting for next run via GitHub Actions.")


if __name__ == "__main__":
    run_all()
