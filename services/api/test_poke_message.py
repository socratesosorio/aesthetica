"""Smoke test: actually send a Poke message for both code paths.

Prints the exact payload, then sends it for real via PokeNotifier.
"""

import sys, os

# Load .env from project root so pydantic-settings picks up POKE_API_KEY
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "api"))

from app.services.notifier import PokeNotifier
import app.services.catalog_from_image as mod


# ── fake data ────────────────────────────────────────────────────────
SIGNAL = {
    "garment_name": "vintage denim jacket",
    "brand_hint": "Levi's",
}

LENS_TOP = {
    "title": "Levi's Vintage Fit Trucker Jacket",
    "product_url": "https://www.levi.com/US/en_US/clothing/men/outerwear/vintage-fit-trucker-jacket/p/773800023",
    "price_text": "$108",
    "price_value": 108.0,
    "image_url": "https://lsco.scene7.com/is/image/lsco/773800023-front-pdp",
}

RANKED = [
    {
        "title": "Levi's Type III Trucker Jacket",
        "product_url": "https://www.levi.com/US/en_US/clothing/men/outerwear/type-iii-trucker-jacket/p/723340001",
        "price_text": "$98",
        "price_value": 98.0,
        "image_url": "https://lsco.scene7.com/is/image/lsco/723340001-front-pdp",
    },
    {
        "title": "Wrangler Icons Denim Jacket",
        "product_url": "https://www.wrangler.com/shop/icons-denim-jacket-WI4012.html",
        "price_text": "$89",
        "price_value": 89.0,
        "image_url": "https://www.wrangler.com/dw/image/v2/AAFF_PRD/on/demandware.static/WI4012.jpg",
    },
]

OPENER = "[TEST] ok this denim jacket is giving main character energy"


# ── monkey-patch the two external calls ──────────────────────────────
_real_opener = mod._generate_poke_opener
_real_lens = mod._lens_to_shopping_context

mod._generate_poke_opener = lambda details: OPENER
mod._lens_to_shopping_context = lambda url, cfg: {
    "description": "Levi's vintage denim trucker jacket",
    "shopping": [LENS_TOP],
}

# ── wrap PokeNotifier.send to print payload before sending ───────────
_real_send = PokeNotifier.send

def _debug_send(self, message, image_url=None):
    print(f"\n--- PAYLOAD message ---\n{message}")
    print(f"\n--- PAYLOAD image_url ---\n{image_url}")
    _real_send(self, message, image_url=image_url)

PokeNotifier.send = _debug_send


# ── run ──────────────────────────────────────────────────────────────
def send_test(label, use_lens=True, ranked=None):
    ranked = ranked or []
    if use_lens:
        mod._lens_to_shopping_context = lambda url, cfg: {
            "description": "Levi's vintage denim trucker jacket",
            "shopping": [LENS_TOP],
        }
    else:
        mod._lens_to_shopping_context = lambda url, cfg: {
            "description": "Levi's vintage denim trucker jacket",
            "shopping": [],
        }

    print(f"\n{'=' * 60}")
    print(f"  SENDING: {label}")
    print(f"{'=' * 60}")

    mod._notify_poke(
        SIGNAL,
        ranked,
        input_image_url="https://storage.example.com/captures/abc123.jpg" if use_lens else None,
        request_id=42,
    )

    print(f"\n  sent!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    print("\n>>> lens_top path — will send 2 messages: link first, then text")
    send_test("lens_top path", use_lens=True)

    # restore
    mod._generate_poke_opener = _real_opener
    mod._lens_to_shopping_context = _real_lens
    PokeNotifier.send = _real_send
