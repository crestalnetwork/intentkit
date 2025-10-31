from pydantic import BaseModel


class TokenModel(BaseModel):
    address: str | None = None
    name: str | None = None
    symbol: str | None = None


class TxnsDetailsModel(BaseModel):
    buys: int | None = None
    sells: int | None = None


class TxnsModel(BaseModel):
    m5: TxnsDetailsModel | None = None
    h1: TxnsDetailsModel | None = None
    h6: TxnsDetailsModel | None = None
    h24: TxnsDetailsModel | None = None


class VolumeModel(BaseModel):
    h24: float | None = None
    h6: float | None = None
    h1: float | None = None
    m5: float | None = None


class PriceChangeModel(BaseModel):
    m5: float | None = None
    h1: float | None = None
    h6: float | None = None
    h24: float | None = None


class LiquidityModel(BaseModel):
    usd: float | None = None
    base: float | None = None
    quote: float | None = None


class WebsiteModel(BaseModel):
    label: str | None = None
    url: str | None = None


class SocialModel(BaseModel):
    type: str | None = None
    url: str | None = None


class InfoModel(BaseModel):
    imageUrl: str | None = None
    websites: list[WebsiteModel | None] | None = None
    socials: list[SocialModel | None] | None = None


class PairModel(BaseModel):
    chainId: str | None = None
    dexId: str | None = None
    url: str | None = None
    pairAddress: str | None = None
    labels: list[str | None] | None = None
    baseToken: TokenModel | None = None
    quoteToken: TokenModel | None = None
    priceNative: str | None = None
    priceUsd: str | None = None
    txns: TxnsModel | None = None
    volume: VolumeModel | None = None
    priceChange: PriceChangeModel | None = None
    liquidity: LiquidityModel | None = None
    fdv: float | None = None
    marketCap: float | None = None
    pairCreatedAt: int | None = None
    info: InfoModel | None = None


class SearchTokenResponseModel(BaseModel):
    schemaVersion: str | None = None
    pairs: list[PairModel | None] | None = None
