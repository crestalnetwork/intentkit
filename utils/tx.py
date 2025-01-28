from pydantic import BaseModel, Field


class EvmTx(BaseModel):
    data: str = Field(None, description="Data of the transaction.")
    to: str = Field(None, description="Address of the receiver of the transaction.")
    from_: str = Field(None, description="Address of the sender of the transaction.")
    value: str = Field(None, description="Amount of token to send.")
    gas: int | None = Field(None, description="Gas amount.")
    gasPrice: int | None = Field(None, description="Gas Price.")
    nonce: int | None = Field(None, description="Nonce of transaction.")
