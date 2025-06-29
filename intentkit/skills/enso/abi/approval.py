ABI_APPROVAL = [
    {
        "inputs": [
            {"internalType": "address", "name": "owner_", "type": "address"},
            {"internalType": "address", "name": "executor_", "type": "address"},
        ],
        "stateMutability": "nonpayable",
        "type": "constructor",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "command_index", "type": "uint256"},
            {"internalType": "address", "name": "target", "type": "address"},
            {"internalType": "string", "name": "message", "type": "string"},
        ],
        "name": "ExecutionFailed",
        "type": "error",
    },
    {"inputs": [], "name": "InvalidAccount", "type": "error"},
    {"inputs": [], "name": "InvalidArrayLength", "type": "error"},
    {"inputs": [], "name": "NotPermitted", "type": "error"},
    {"inputs": [], "name": "UnsafeSetting", "type": "error"},
    {"inputs": [], "name": "WithdrawFailed", "type": "error"},
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "bytes32",
                "name": "role",
                "type": "bytes32",
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "account",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "bool",
                "name": "permission",
                "type": "bool",
            },
        ],
        "name": "PermissionSet",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "EXECUTOR_ROLE",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "MODULE_ROLE",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "OWNER_ROLE",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32[]", "name": "commands", "type": "bytes32[]"},
            {"internalType": "bytes[]", "name": "state", "type": "bytes[]"},
        ],
        "name": "executeShortcut",
        "outputs": [{"internalType": "bytes[]", "name": "", "type": "bytes[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "executor",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "role", "type": "bytes32"},
            {"internalType": "address", "name": "account", "type": "address"},
        ],
        "name": "getPermission",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "name": "onERC1155BatchReceived",
        "outputs": [{"internalType": "bytes4", "name": "", "type": "bytes4"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "name": "onERC1155Received",
        "outputs": [{"internalType": "bytes4", "name": "", "type": "bytes4"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "name": "onERC721Received",
        "outputs": [{"internalType": "bytes4", "name": "", "type": "bytes4"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "internalType": "enum MinimalWallet.Protocol",
                        "name": "protocol",
                        "type": "uint8",
                    },
                    {"internalType": "address", "name": "token", "type": "address"},
                    {
                        "internalType": "address[]",
                        "name": "operators",
                        "type": "address[]",
                    },
                ],
                "internalType": "struct MinimalWallet.ApprovalNote[]",
                "name": "notes",
                "type": "tuple[]",
            }
        ],
        "name": "revokeApprovals",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC1155", "name": "erc1155", "type": "address"},
            {"internalType": "address[]", "name": "operators", "type": "address[]"},
        ],
        "name": "revokeERC1155Approvals",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC20", "name": "erc20", "type": "address"},
            {"internalType": "address[]", "name": "operators", "type": "address[]"},
        ],
        "name": "revokeERC20Approvals",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC721", "name": "erc721", "type": "address"},
            {"internalType": "address[]", "name": "operators", "type": "address[]"},
        ],
        "name": "revokeERC721Approvals",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "role", "type": "bytes32"},
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "bool", "name": "permission", "type": "bool"},
        ],
        "name": "setPermission",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes4", "name": "interfaceId", "type": "bytes4"}],
        "name": "supportsInterface",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "internalType": "enum MinimalWallet.Protocol",
                        "name": "protocol",
                        "type": "uint8",
                    },
                    {"internalType": "address", "name": "token", "type": "address"},
                    {"internalType": "uint256[]", "name": "ids", "type": "uint256[]"},
                    {
                        "internalType": "uint256[]",
                        "name": "amounts",
                        "type": "uint256[]",
                    },
                ],
                "internalType": "struct MinimalWallet.TransferNote[]",
                "name": "notes",
                "type": "tuple[]",
            }
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC1155", "name": "erc1155", "type": "address"},
            {"internalType": "uint256[]", "name": "ids", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"},
        ],
        "name": "withdrawERC1155s",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "internalType": "contract IERC20[]",
                "name": "erc20s",
                "type": "address[]",
            },
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"},
        ],
        "name": "withdrawERC20s",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "contract IERC721", "name": "erc721", "type": "address"},
            {"internalType": "uint256[]", "name": "ids", "type": "uint256[]"},
        ],
        "name": "withdrawERC721s",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "withdrawETH",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {"stateMutability": "payable", "type": "receive"},
]
