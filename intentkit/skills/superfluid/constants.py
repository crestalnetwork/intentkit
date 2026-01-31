"""Constants for Superfluid skills."""

# Superfluid Host contract address (same on all EVM chains)
SUPERFLUID_HOST_ADDRESS = "0xcfA132E353cB4E398080B9700609bb008eceB125"

CREATE_FLOW_ABI: list[dict] = [
    {
        "inputs": [
            {
                "internalType": "contract ISuperToken",
                "name": "token",
                "type": "address",
            },
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "int96", "name": "flowrate", "type": "int96"},
            {"internalType": "bytes", "name": "userData", "type": "bytes"},
        ],
        "name": "createFlow",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

UPDATE_FLOW_ABI: list[dict] = [
    {
        "inputs": [
            {
                "internalType": "contract ISuperToken",
                "name": "token",
                "type": "address",
            },
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "int96", "name": "flowrate", "type": "int96"},
            {"internalType": "bytes", "name": "userData", "type": "bytes"},
        ],
        "name": "updateFlow",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

DELETE_FLOW_ABI: list[dict] = [
    {
        "inputs": [
            {
                "internalType": "contract ISuperToken",
                "name": "token",
                "type": "address",
            },
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "bytes", "name": "userData", "type": "bytes"},
        ],
        "name": "deleteFlow",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]
