"""
Temporary script to exercise the x402_check_price skill against a local seller.

Usage:
    python intentkit/scripts/test_x402_check_price.py \
        --url http://localhost:8001/services/amazon-place-order \
        --asin B012345678

Notes:
- This script only checks the payment requirements (price) and does not pay.
- It uses the x402_check_price skill directly.
"""

import argparse
import asyncio
import json
from typing import Any

from intentkit.skills.x402.check_price import X402CheckPrice


def _build_payload(
    asin: str,
    name: str,
    address_line_1: str,
    city: str,
    state: str,
    postal_code: str,
    country: str,
    phone: str,
) -> dict[str, Any]:
    return {
        "asin": asin,
        "shipping_address": {
            "name": name,
            "address_line_1": address_line_1,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "phone": phone,
        },
    }


async def _run(args: argparse.Namespace) -> None:
    skill = X402CheckPrice()
    payload = _build_payload(
        asin=args.asin,
        name=args.name,
        address_line_1=args.address_line_1,
        city=args.city,
        state=args.state,
        postal_code=args.postal_code,
        country=args.country,
        phone=args.phone,
    )

    if args.verbose:
        print("Request payload:")
        print(json.dumps(payload, indent=2))

    result = await skill._arun(  # noqa: SLF001
        method=args.method,
        url=args.url,
        headers=None,
        params=None,
        data=payload,
        timeout=args.timeout,
    )
    print(result)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the x402_check_price skill against a local seller."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Absolute URL for the 402-protected endpoint.",
    )
    parser.add_argument(
        "--method",
        default="POST",
        choices=["GET", "POST"],
        help="HTTP method to use (default: POST).",
    )
    parser.add_argument(
        "--asin",
        required=True,
        help="ASIN to check.",
    )
    parser.add_argument(
        "--name",
        default="Alexander J. Thompson",
        help="Recipient name.",
    )
    parser.add_argument(
        "--address-line-1",
        default="1248 Oakwood Avenue",
        dest="address_line_1",
        help="Street address line 1.",
    )
    parser.add_argument(
        "--city",
        default="San Francisco",
        help="City.",
    )
    parser.add_argument(
        "--state",
        default="CA",
        help="State or region.",
    )
    parser.add_argument(
        "--postal-code",
        default="94110",
        dest="postal_code",
        help="Postal code.",
    )
    parser.add_argument(
        "--country",
        default="USA",
        help="Country.",
    )
    parser.add_argument(
        "--phone",
        default="+1 (415) 555-0198",
        help="Phone number.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print request payload.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
