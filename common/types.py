"""
sync/types.py

This file defines type aliases and TypedDicts used in the Flashbots module.
"""

from enum import Enum
from typing import List, Optional, TypedDict, Union

from eth_account.signers.local import LocalAccount
from eth_typing import URI, HexStr
from hexbytes import HexBytes
from web3.types import TxParams, _Hash32

FlashbotsBundleTx = TypedDict(
    "FlashbotsBundleTx",
    {"transaction": TxParams, "signer": LocalAccount},
)

FlashbotsBundleRawTx = TypedDict(
    "FlashbotsBundleRawTx",
    {"signed_transaction": HexBytes},
)

FlashbotsBundleDictTx = TypedDict(
    "FlashbotsBundleDictTx",
    {
        "accessList": list,
        "blockHash": HexBytes,
        "blockNumber": int,
        "chainId": str,
        "from": str,
        "gas": int,
        "gasPrice": int,
        "maxFeePerGas": int,
        "maxPriorityFeePerGas": int,
        "hash": HexBytes,
        "input": str,
        "nonce": int,
        "r": HexBytes,
        "s": HexBytes,
        "to": str,
        "transactionIndex": int,
        "type": str,
        "v": int,
        "value": int,
    },
    total=False,
)

FlashbotsOpts = TypedDict(
    "FlashbotsOpts",
    {
        "minTimestamp": Optional[int],
        "maxTimestamp": Optional[int],
        "revertingTxHashes": Optional[List[str]],
        "replacementUuid": Optional[str],
    },
)

SignTx = TypedDict(
    "SignTx",
    {
        "nonce": int,
        "chainId": int,
        "to": str,
        "data": str,
        "value": int,
        "gas": int,
        "gasPrice": int,
    },
    total=False,
)

TxReceipt = Union[_Hash32, HexBytes, HexStr]

SignedTxAndHash = TypedDict(
    "SignedTxAndHash",
    {"signed_transaction": str, "hash": HexBytes},
)

class Network(Enum):
    SEPOLIA = "sepolia"
    HOLESKY = "holesky"
    MAINNET = "mainnet"

class NetworkConfig(TypedDict):
    chain_id: int
    provider_url: URI
    relay_url: URI
