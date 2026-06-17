import requests
import time
import json
import os
from bs4 import BeautifulSoup

NSSF_BASE_URL = "https://www.nssfug.org"

PAGES_TO_SCRAPE = [
    "/",
    "/real-estate",
    "/benefits-products",
    "/self-service",
    "/opportunities",
    "/media-centre",
    "/about-us",
    "/contact-us",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── SETTINGS ─────────────────────────────────────────────────────────────────
CACHE_FILE = "nssf_cache.json"   # Saved scrape data lives here
MAX_RETRIES = 5                   # How many times to retry a failed page
RETRY_DELAY = 10                  # Seconds to wait between retries
SITE_CHECK_INTERVAL = 30          # Seconds to wait before rechecking if site is down


# ─── CACHE HELPERS ────────────────────────────────────────────────────────────

def save_cache(data: str):
    """Save scraped content to a local cache file."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"content": data}, f)
    print(f"[Scraper] 💾 Content saved to cache: {CACHE_FILE}")


def load_cache() -> str:
    """Load previously scraped content from cache if it exists."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Scraper] 📂 Loaded content from cache: {CACHE_FILE}")
        return data.get("content", "")
    return ""


# ─── SITE AVAILABILITY CHECK ──────────────────────────────────────────────────

def is_site_up() -> bool:
    """Check if the NSSF homepage is reachable."""
    try:
        response = requests.get(NSSF_BASE_URL, headers=HEADERS, timeout=8)
        # Treat anything below 500 as "up" (even 404 means server is responding)
        return response.status_code < 500
    except requests.RequestException:
        return False


def wait_for_site():
    """Block until the NSSF site is reachable, checking every 30 seconds."""
    print(f"\n[Scraper] ⏳ NSSF website appears to be down or under maintenance.")
    print(f"[Scraper] Will keep checking every {SITE_CHECK_INTERVAL} seconds until it's back up...")
    print(f"[Scraper] Press CTRL+C at any time to cancel and use cached data instead.\n")

    attempt = 1
    while True:
        try:
            print(f"[Scraper] 🔁 Check #{attempt} — pinging {NSSF_BASE_URL} ...")
            if is_site_up():
                print(f"[Scraper] ✅ Site is back up! Starting scrape...\n")
                return
            else:
                print(f"[Scraper] ❌ Still down. Waiting {SITE_CHECK_INTERVAL} seconds...\n")
                time.sleep(SITE_CHECK_INTERVAL)
                attempt += 1
        except KeyboardInterrupt:
            print("\n[Scraper] ⚠️  Retry cancelled by user.")
            raise


# ─── PAGE SCRAPER ─────────────────────────────────────────────────────────────

def scrape_page(path: str) -> dict:
    """Scrape a single page with retry logic."""
    url = NSSF_BASE_URL + path

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title else path
            content = soup.get_text(separator="\n", strip=True)

            # Collapse blank lines
            lines = [line for line in content.splitlines() if line.strip()]
            clean_content = "\n".join(lines)

            return {"url": url, "title": title, "content": clean_content}

        except requests.RequestException as e:
            print(f"[Scraper] ⚠️  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}")
            if attempt < MAX_RETRIES:
                print(f"[Scraper] Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[Scraper] ❌ Giving up on {url} after {MAX_RETRIES} attempts.")

    return {"url": url, "title": "", "content": ""}


# ─── MAIN SCRAPE FUNCTION ─────────────────────────────────────────────────────

def scrape_all_pages() -> str:
    """
    Main entry point for scraping.
    - If cached data exists, offers to use it immediately.
    - If site is down, waits and retries automatically.
    - Once scraped successfully, saves to cache.
    """

    # ── Step 1: Check for existing cache ──
    cached = load_cache()
    if cached:
        print("[Scraper] 📦 Found existing cached data.")
        print("[Scraper] Type 'yes' to use cache, or 'no' to wait for site and re-scrape: ", end="")
        choice = input().strip().lower()
        if choice == "yes":
            return cached
        else:
            print("[Scraper] OK — will wait for site to come back up and re-scrape.")

    # ── Step 2: Wait for site if it's down ──
    if not is_site_up():
        try:
            wait_for_site()
        except KeyboardInterrupt:
            # User cancelled — fall back to cache if available
            if cached:
                print("[Scraper] Using cached data as fallback.")
                return cached
            else:
                print("[Scraper] No cache available. Exiting.")
                return ""

    # ── Step 3: Scrape all pages ──
    print("[Scraper] 🌐 Starting NSSF Uganda website scrape...")
    all_text = []

    for path in PAGES_TO_SCRAPE:
        data = scrape_page(path)
        if data["content"]:
            section = (
                f"=== PAGE: {data['title']} ===\n"
                f"URL: {data['url']}\n\n"
                f"{data['content']}\n"
            )
            all_text.append(section)
            print(f"[Scraper] ✅ Scraped: {data['title'] or path}")
        else:
            print(f"[Scraper] ⚠️  Skipped (no content): {path}")

    combined = "\n\n".join(all_text)

    # ── Step 4: Save to cache ──
    if combined.strip():
        save_cache(combined)
        print(f"[Scraper] ✅ Done. Total characters scraped: {len(combined)}")
    else:
        print("[Scraper] ⚠️  Nothing was scraped — site may still be having issues.")

    return combined