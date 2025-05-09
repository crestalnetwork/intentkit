from typing import List, Optional

from pydantic import BaseModel


class TokenModel(BaseModel):
    address: Optional[str] = None
    name: Optional[str] = None
    symbol: Optional[str] = None


class TxnsDetailsModel(BaseModel):
    buys: Optional[int] = None
    sells: Optional[int] = None


class TxnsModel(BaseModel):
    m5: Optional[TxnsDetailsModel] = None
    h1: Optional[TxnsDetailsModel] = None
    h6: Optional[TxnsDetailsModel] = None
    h24: Optional[TxnsDetailsModel] = None


class VolumeModel(BaseModel):
    h24: Optional[float] = None
    h6: Optional[float] = None
    h1: Optional[float] = None
    m5: Optional[float] = None


class PriceChangeModel(BaseModel):
    m5: Optional[float] = None
    h1: Optional[float] = None
    h6: Optional[float] = None
    h24: Optional[float] = None


class LiquidityModel(BaseModel):
    usd: Optional[float] = None
    base: Optional[float] = None
    quote: Optional[float] = None


class WebsiteModel(BaseModel):
    label: Optional[str] = None
    url: Optional[str] = None


class SocialModel(BaseModel):
    type: Optional[str] = None
    url: Optional[str] = None


class InfoModel(BaseModel):
    imageUrl: Optional[str] = None
    websites: Optional[List[Optional[WebsiteModel]]] = None
    socials: Optional[List[Optional[SocialModel]]] = None


class PairModel(BaseModel):
    chainId: Optional[str] = None
    dexId: Optional[str] = None
    url: Optional[str] = None
    pairAddress: Optional[str] = None
    labels: Optional[List[Optional[str]]] = None
    baseToken: Optional[TokenModel] = None
    quoteToken: Optional[TokenModel] = None
    priceNative: Optional[str] = None
    priceUsd: Optional[str] = None
    txns: Optional[TxnsModel] = None
    volume: Optional[VolumeModel] = None
    priceChange: Optional[PriceChangeModel] = None
    liquidity: Optional[LiquidityModel] = None
    fdv: Optional[float] = None
    marketCap: Optional[float] = None
    pairCreatedAt: Optional[int] = None
    info: Optional[InfoModel] = None


class SearchTokenResponseModel(BaseModel):
    schemaVersion: Optional[str] = None
    pairs: Optional[List[Optional[PairModel]]] = None
