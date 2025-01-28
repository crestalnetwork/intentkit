from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from utils.tx import EvmTx

from .base import CdpBaseTool

ENSO_ROUTE_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "owner_", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "constructor",
    },
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
        "name": "AmountTooLow",
        "type": "error",
    },
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
        "name": "Duplicate",
        "type": "error",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "WrongValue",
        "type": "error",
    },
    {
        "inputs": [],
        "name": "enso",
        "outputs": [
            {"internalType": "contract EnsoShortcuts", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "internalType": "contract IERC20",
                        "name": "token",
                        "type": "address",
                    },
                    {"internalType": "uint256", "name": "amount", "type": "uint256"},
                ],
                "internalType": "struct Token[]",
                "name": "tokensIn",
                "type": "tuple[]",
            },
            {"internalType": "bytes32[]", "name": "commands", "type": "bytes32[]"},
            {"internalType": "bytes[]", "name": "state", "type": "bytes[]"},
        ],
        "name": "routeMulti",
        "outputs": [
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC20", "name": "tokenIn", "type": "address"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "bytes32[]", "name": "commands", "type": "bytes32[]"},
            {"internalType": "bytes[]", "name": "state", "type": "bytes[]"},
        ],
        "name": "routeSingle",
        "outputs": [
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "internalType": "contract IERC20",
                        "name": "token",
                        "type": "address",
                    },
                    {"internalType": "uint256", "name": "amount", "type": "uint256"},
                ],
                "internalType": "struct Token[]",
                "name": "tokensIn",
                "type": "tuple[]",
            },
            {
                "components": [
                    {
                        "internalType": "contract IERC20",
                        "name": "token",
                        "type": "address",
                    },
                    {"internalType": "uint256", "name": "amount", "type": "uint256"},
                ],
                "internalType": "struct Token[]",
                "name": "tokensOut",
                "type": "tuple[]",
            },
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "bytes32[]", "name": "commands", "type": "bytes32[]"},
            {"internalType": "bytes[]", "name": "state", "type": "bytes[]"},
        ],
        "name": "safeRouteMulti",
        "outputs": [
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC20", "name": "tokenIn", "type": "address"},
            {"internalType": "contract IERC20", "name": "tokenOut", "type": "address"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "minAmountOut", "type": "uint256"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "bytes32[]", "name": "commands", "type": "bytes32[]"},
            {"internalType": "bytes[]", "name": "state", "type": "bytes[]"},
        ],
        "name": "safeRouteSingle",
        "outputs": [
            {"internalType": "bytes[]", "name": "returnData", "type": "bytes[]"}
        ],
        "stateMutability": "payable",
        "type": "function",
    },
]


class Transaction(BaseModel):
    data: str = Field(None, description="Data of the transaction.")
    to: str = Field(
        None, description="Ethereum address of the receiver of the transaction."
    )
    from_: str = Field(
        None, description="Ethereum address of the sender of the transaction."
    )
    value: str = Field(None, description="Amount of token to send.")


class CdpBroadcastEnsoTxInput(BaseModel):
    """
    Input model for broadcasting a transaction.
    """

    txRef: str = Field(
        description="should be filled by you according to your memory from txRef."
    )


class CdpBroadcastEnsoTxOutput(BaseModel):
    """
    Output model for broadcasting a transaction.
    """

    txHash: str = Field(
        description="The transaction hash of the broadcasted transaction."
    )


class CdpBroadcastEnsoTx(CdpBaseTool):
    """
    This tool broadcasts a transaction using the transaction data provided. the tx data should be
    stored in your memory via Enso shortcut route tool. if users asks to broadcast the transaction by reference code
    you should retrieve the transaction data from your memory and send it to this tool.

    Attributes:
        name (str): Name of the tool, specifically "cdp_broadcast_tx".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "cdp_broadcast_tx"
    description: str = "This tool broadcasts transaction using the calldata transaction body generated by the EnsoGetRouteShortcut tool which will be passed to you by user as a confirmation."
    args_schema: Type[BaseModel] = CdpBroadcastEnsoTxInput

    def _run(self, txRef: str) -> CdpBroadcastEnsoTxOutput:
        """
        Run the tool to get swap route information.

        Args:
            txRef (str): Transaction reference code generated by EnsoGetRouteShortcut tool and will be passed by user as a confirmation.

        Returns:
            CdpBroadcastTxOutput: The response containing route shortcut information.
        """

        try:
            w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
            contract = w3.eth.contract(abi=ENSO_ROUTE_ABI)

            tx = self.store.get_agent_skill_data(
                self.agent_id, "enso_get_route_shortcut", txRef
            )

            evm_tx = EvmTx(**tx)
            fn, fn_args = contract.decode_function_input(evm_tx.data)

            fn_args["amountIn"] = str(fn_args["amountIn"])

            for i, arg in fn_args.items():
                if isinstance(arg, bytes):
                    fn_args[i] = arg.hex()  # Convert bytes to hexadecimal string
                elif isinstance(arg, list) and all(
                    isinstance(item, bytes) for item in arg
                ):
                    fn_args[i] = [
                        item.hex() for item in arg
                    ]  # Convert list of bytes to list of hex strings

            invocation = self.wallet.invoke_contract(
                contract_address=evm_tx.to,
                method=fn.fn_name,
                abi=ENSO_ROUTE_ABI,
                args=fn_args,
            ).wait()

            return CdpBroadcastEnsoTxOutput(
                txHash=invocation.transaction.transaction_hash
            )
        except Exception as e:
            raise ToolException(f"error from cdp contract call: {e}") from e
