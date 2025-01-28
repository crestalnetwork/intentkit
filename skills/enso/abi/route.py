ABI_ROUTE = [
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
