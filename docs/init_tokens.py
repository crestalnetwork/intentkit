import asyncio
import json
import time

import requests
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from models.w3 import W3Token

# Database URL (replace with your actual database URL)
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/intentkit"

# Create asynchronous engine
engine = create_async_engine(DATABASE_URL)

# Create session factory
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


base_url = "https://api.enso.finance/api/v1/tokens"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer 1e02632d-6feb-4a75-a157-documentation",
}
chain_ids = [
    # 1, # Ethereum Mainnet
    8453,
    # 42161, # Arbitrum
]


async def add_to_db(item):
    sym = item.get("symbol")
    if sym and sym.strip() != "":
        chid = str(item.get("chainId"))
        async for db in get_session():
            existing = (
                await db.execute(
                    select(W3Token).where(
                        W3Token.symbol == sym,
                        W3Token.chain_id == chid,
                    )
                )
            ).first()
            if not existing:
                new_token = W3Token(
                    symbol=sym,
                    chain_id=chid,
                    name=item.get("name"),
                    decimals=item.get("decimals"),
                    address=item.get("address"),
                    primary_address=item.get("primaryAddress"),
                    is_well_known=False,
                    protocol_slug=item.get("protocolSlug"),
                    token_type=item.get("type"),
                )
                db.add(new_token)

            await db.commit()


async def main():
    for ch_id in chain_ids:
        page = 1
        while True:
            url = f"{base_url}?&chainId={ch_id}&page={page}&includeMetadata=true"
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()
                meta = data.get("meta", {})
                tokens = data.get("data", [])  # access the items list
                if (
                    not tokens
                ):  # if the items list is empty, then break out of the loop.
                    break
                print(f"processing chain {ch_id} page {page} of {meta["lastPage"]}")
                for item in tokens:
                    if item.get("underlyingTokens"):
                        for t in item["underlyingTokens"]:
                            await add_to_db(t)
                    await add_to_db(item)
                page += 1
                if page > int(meta["lastPage"]):
                    break
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                print(f"Error fetching page {page}: {e}")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON on page {page}: {e}")
            except KeyError as e:
                print(f"Error accessing 'items' in the JSON on page {page}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
