from pydantic import BaseModel, Field
from web3 import Web3


class EvmContractWrapper:
    def __init__(self, rpc_url: str, abi: list[dict], tx_data: str):
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        contract = w3.eth.contract(abi=abi)

        self.evm_tx = EvmTx(**tx_data)
        self.fn, self.fn_args = contract.decode_function_input(self.evm_tx.data)

        for i, arg in self.fn_args.items():
            if isinstance(arg, bytes):
                self.fn_args[i] = arg.hex()  # Convert bytes to hexadecimal string
            elif isinstance(arg, list) and all(isinstance(item, bytes) for item in arg):
                self.fn_args[i] = [
                    item.hex() for item in arg
                ]  # Convert list of bytes to list of hex strings

    @property
    def fn_and_args(self):
        return self.fn, self.fn_args

    @property
    def dst_addr(self):
        return self.evm_tx.to


class EvmTx(BaseModel):
    data: str = Field(None, description="Data of the transaction.")
    to: str = Field(None, description="Address of the receiver of the transaction.")
    from_: str = Field(None, description="Address of the sender of the transaction.")
    value: str = Field(None, description="Amount of token to send.")
    gas: int | None = Field(None, description="Gas amount.")
    gasPrice: int | None = Field(None, description="Gas Price.")
    nonce: int | None = Field(None, description="Nonce of transaction.")
