"""
NSSF ingestion pipeline (Playwright version, thorough scrape).

  Extract   -> load each page in a real (headless) browser so JavaScript
               content renders, scroll to trigger lazy content, read the text
  Transform -> split into chunks, embed each chunk with Gemini
  Load      -> store the vectors + text in Qdrant

One-time setup (in your activated .venv):
    pip install playwright python-dotenv
    playwright install chromium

Usage (with Qdrant running and the key in .env):
    python ingest.py
"""
import os
import re
import uuid
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from openai import AzureOpenAI
from playwright.sync_api import sync_playwright
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

#OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
COLLECTION = os.environ.get("COLLECTION", "nssf")

AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
AZURE_EMBED_DEPLOYMENT = os.environ.get("AZURE_EMBED_DEPLOYMENT", AZURE_DEPLOYMENT)
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# Optional separate embedding resource (endpoint + key). If provided, the
# ingestion pipeline will call the embedding deployment on that resource.
AZURE_EMBED_ENDPOINT = os.environ.get("AZURE_EMBED_ENDPOINT", "")
AZURE_EMBED_API_KEY = os.environ.get("AZURE_EMBED_API_KEY", "")

if AZURE_ENDPOINT:
    client = AzureOpenAI(
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
    )
else:
    client = None

# embedding client: prefer explicit embed endpoint/key when provided
if AZURE_EMBED_ENDPOINT:
    embed_client = AzureOpenAI(
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_EMBED_ENDPOINT,
        api_key=AZURE_EMBED_API_KEY,
    )
elif client is not None:
    embed_client = client
else:
    raise RuntimeError(
        "No Azure endpoint configured. Set AZURE_OPENAI_ENDPOINT or AZURE_EMBED_ENDPOINT in .env before running ingestion."
    )

# Use the embed deployment if provided, otherwise fall back to general
EMBED_MODEL = AZURE_EMBED_DEPLOYMENT

# Diagnostic info to help debug 404 deployment-not-found errors.
print("[ingest] embed endpoint:", AZURE_EMBED_ENDPOINT or AZURE_ENDPOINT)
print("[ingest] embed api key present:", bool(AZURE_EMBED_API_KEY or AZURE_API_KEY))
print("[ingest] embed deployment:", EMBED_MODEL)

SEED_URLS = [
    "https://www.nssfug.org/",
    "https://www.nssfug.org/about-us/mission/",
    "https://www.nssfug.org/about-us/membership/",
    "https://www.nssfug.org/about-us/purpose/",
    "https://www.nssfug.org/about-us/investments/",
    "https://www.nssfug.org/benefits-products/benefits/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-age/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-withdrawal/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-survivors/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-invalidity/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-exempted/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-midterm/",
    "https://www.nssfug.org/benefits-products/benefits/benefits-emigration/",
    "https://www.nssfug.org/smartlifeflexi/",
    "https://www.nssfug.org/benefits-products/smart-card/",
    "https://www.nssfug.org/benefits-products/midterm/",
    "https://www.nssfug.org/benefits-products/diaspora-connect/",
    "https://www.nssfug.org/benefits-products/friends-with-benefits/",
    "https://www.nssfug.org/benefits-products/financial-literacy/",
    "https://www.nssfug.org/media-center/legal/nssf-act/",
    "https://www.nssfug.org/media-center/legal/nssf-regulations/",
    "https://www.nssfug.org/media-center/legal/nssf-ammendments/",
    "https://www.nssfug.org/media-center/legal/privacy-statement/",
    "https://www.nssfug.org/contactus/",
]

qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY or None,
)

CURATED_DOCS = [
    {
        "text": "NSSF (National Social Security Fund) Uganda is a provident fund "
        "that covers all employees in the private sector who are not covered by "
        "the government pension scheme. It collects contributions from members "
        "and their employers, invests them, and pays benefits to members.",
        "url": "https://www.nssfug.org/about-us/mission/",
    },
    {
        "text": "To register as an individual NSSF member, use the NSSFGo app or "
        "register online at https://nssfgo.app/register/new-member . You will "
        "need your personal identification details. Employers register their "
        "company at https://nssfgo.app/register/new-company .",
        "url": "https://nssfgo.app/register/new-member",
    },
    {
        "text": "To check your NSSF balance, log in to the NSSFGo app or visit "
        "https://nssfgo.app/landing . You can also request a mini statement "
        "through the same app. Toll free customer care: 0800286773.",
        "url": "https://nssfgo.app/landing",
    },
    {
        "text": "To make a contribution, use the NSSFGo app at "
        "https://nssfgo.app/landing?redirect=make-contribution . Employers use "
        "the E-collections portal to remit employee contributions.",
        "url": "https://nssfgo.app/landing?redirect=make-contribution",
    },
    {
        "text": "To submit a benefits claim, use the NSSFGo app at "
        "https://nssfgo.app/landing?redirect=claim-benefit . You can track the "
        "status of your claim in the app without visiting a branch.",
        "url": "https://nssfgo.app/landing?redirect=claim-benefit",
    },
    {
        "text": "NSSF Uganda customer service: toll free 0800286773, phone "
        "+256312234400, email customerservice@nssfug.org. Head office: Workers "
        "House, 14th Floor, Plot 1 Pilkington Road, Kampala.",
        "url": "https://www.nssfug.org/contactus/",
    },
]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def scrape_all(urls: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="nssf-chatbot-ingest/1.0")
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                # Wait for a real content area to appear.
                try:
                    page.wait_for_selector("main, article, .content, body", timeout=15000)
                except Exception:
                    pass
                # Scroll down to trigger lazy-loaded sections.
                for _ in range(5):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(500)
                page.wait_for_timeout(2000)  # let everything settle
                text = clean(page.inner_text("body"))
                results[url] = text
                status = "OK" if len(text) > 300 else "THIN - check this page"
                print(f"  scraped {url}: {len(text)} chars [{status}]")
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {url}: {exc}")
        browser.close()
    return results


def chunk(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        i += size - overlap
    return [c for c in chunks if len(c) > 50]


def embed_batch(texts: list[str]) -> list[list[float]]:
    vectors = []
    for i in range(0, len(texts), 64):
        batch = texts[i : i + 64]
        try:
            resp = embed_client.embeddings.create(model=EMBED_MODEL, input=batch)
            vectors.extend(d.embedding for d in resp.data)
        except Exception as exc:  # capture detailed info for debugging
            print("[ingest] embedding request failed:", repr(exc))
            # If the AzureOpenAI client surfaces a response body, print it.
            try:
                # some SDK errors include a 'response' attribute
                print("[ingest] error details:", getattr(exc, 'response', None))
            except Exception:
                pass
            raise
    return vectors


def ensure_collection(dim: int) -> None:
    names = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in names:
        qdrant.create_collection(
            COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}' (dim={dim})")


def main() -> None:
    dim = len(embed_batch(["dimension probe"])[0])
    ensure_collection(dim)
    points = []

    # 1. Curated answers for app-based actions and general "what is NSSF".
    curated_texts = [d["text"] for d in CURATED_DOCS]
    curated_vectors = embed_batch(curated_texts)
    for doc, vec in zip(CURATED_DOCS, curated_vectors):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": doc["text"], "url": doc["url"], "source": "NSSF Uganda"},
            )
        )
    print(f"  curated answers: {len(CURATED_DOCS)} chunks")

    # 2. Scrape every page in a real browser, then chunk + embed.
    print("Scraping pages (this opens a headless browser)...")
    pages = scrape_all(SEED_URLS)

    for url, text in pages.items():
        chunks = chunk(text)
        if not chunks:
            continue
        vectors = embed_batch(chunks)
        for ch, vec in zip(chunks, vectors):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload={"text": ch, "url": url, "source": "NSSF Uganda"},
                )
            )
        print(f"  {url}: {len(chunks)} chunks")

    if points:
        qdrant.upsert(COLLECTION, points=points)
        print(f"Done. Upserted {len(points)} chunks into '{COLLECTION}'.")
    else:
        print("No content ingested. Check the SEED_URLS.")


if __name__ == "__main__":
    main()
