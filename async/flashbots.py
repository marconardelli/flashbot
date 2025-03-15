"""
async/flashbots.py

This module implements the asynchronous Flashbots functionality for AsyncWeb3.
It defines methods for signing bundles, sending bundles, cancelling bundles,
simulating bundles, and more.
"""

import asyncio
import logging
from functools import reduce
from typing import Any, Callable, Dict, List, Optional, Union

import rlp
from eth_account import Account
from eth_account._utils.legacy_transactions import (
    Transaction,
    encode_transaction,
    serializable_unsigned_transaction_from_dict,
)
from eth_account.typed_transactions import (
    AccessListTransaction,
    DynamicFeeTransaction,
)
from eth_typing import HexStr
from hexbytes import HexBytes
from toolz import dissoc
from web3 import AsyncWeb3
from web3.exceptions import TransactionNotFound
from web3.method import Method
from web3.module import Module
from web3.types import Nonce, RPCEndpoint, TxParams

from common.types import (
    FlashbotsBundleDictTx,
    FlashbotsBundleRawTx,
    FlashbotsBundleTx,
    FlashbotsOpts,
    SignedTxAndHash,
    TxReceipt,
)

SECONDS_PER_BLOCK = 12

class FlashbotsRPC:
    eth_sendBundle = RPCEndpoint("eth_sendBundle")
    eth_callBundle = RPCEndpoint("eth_callBundle")
    eth_cancelBundle = RPCEndpoint("eth_cancelBundle")
    eth_sendPrivateTransaction = RPCEndpoint("eth_sendPrivateTransaction")
    eth_cancelPrivateTransaction = RPCEndpoint("eth_cancelPrivateTransaction")
    flashbots_getBundleStats = RPCEndpoint("flashbots_getBundleStats")
    flashbots_getUserStats = RPCEndpoint("flashbots_getUserStats")
    flashbots_getBundleStatsV2 = RPCEndpoint("flashbots_getBundleStatsV2")
    flashbots_getUserStatsV2 = RPCEndpoint("flashbots_getUserStatsV2")

class FlashbotsBundleResponse:
    """
    Represents an asynchronous Flashbots bundle response.
    """
    def __init__(self, w3: AsyncWeb3, txs: List[HexBytes], target_block_number: int):
        self.w3 = w3
        self.bundle = [{"signed_transaction": tx, "hash": w3.keccak(tx)} for tx in txs]
        self.target_block_number = target_block_number

    async def wait(self) -> None:
        """Wait until the target block has been reached (async version)."""
        while (await self.w3.eth.block_number) < self.target_block_number:
            await asyncio.sleep(1)

    async def receipts(self) -> List[TxReceipt]:
        """Retrieve transaction receipts for the bundle (async version)."""
        await self.wait()
        return [await self.w3.eth.get_transaction_receipt(tx["hash"]) for tx in self.bundle]

    def bundle_hash(self) -> str:
        concat_hashes = reduce(lambda a, b: a + b, [tx["hash"] for tx in self.bundle])
        return self.w3.keccak(concat_hashes)

class FlashbotsPrivateTransactionResponse:
    """
    Represents an asynchronous Flashbots private transaction response.
    """
    def __init__(self, w3: AsyncWeb3, signed_tx: HexBytes, max_block_number: int):
        self.w3 = w3
        self.max_block_number = max_block_number
        self.tx = {"signed_transaction": signed_tx, "hash": w3.keccak(signed_tx)}

    async def wait(self) -> bool:
        """Wait until the transaction is mined or max block reached."""
        while True:
            try:
                await self.w3.eth.get_transaction(self.tx["hash"])
                return True
            except TransactionNotFound:
                if (await self.w3.eth.block_number) > self.max_block_number:
                    return False
                await asyncio.sleep(1)

    async def receipt(self) -> Optional[TxReceipt]:
        if await self.wait():
            return await self.w3.eth.get_transaction_receipt(self.tx["hash"])
        else:
            return None

class Flashbots(Module):
    """
    The asynchronous Flashbots module attaches methods for bundle operations.
    """
    signed_txs: List[HexBytes]
    response: Union[FlashbotsBundleResponse, FlashbotsPrivateTransactionResponse]
    logger = logging.getLogger("flashbots")

    async def sign_bundle(
        self,
        bundled_transactions: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]]
    ) -> List[HexBytes]:
        """
        Asynchronously sign a list of bundle transactions.
        """
        nonces: Dict[HexStr, Nonce] = {}
        signed_transactions: List[HexBytes] = []
        for tx in bundled_transactions:
            if "signed_transaction" in tx:
                tx_params = _parse_signed_tx(tx["signed_transaction"])
                nonces[tx_params["from"]] = tx_params["nonce"] + 1
                signed_transactions.append(tx["signed_transaction"])
            elif "signer" in tx:
                signer, tx_dict = tx["signer"], tx["transaction"]
                tx_dict["from"] = signer.address
                if tx_dict.get("nonce") is None:
                    tx_dict["nonce"] = nonces.get(signer.address, await self.w3.eth.get_transaction_count(signer.address))
                nonces[signer.address] = tx_dict["nonce"] + 1
                if "gas" not in tx_dict:
                    tx_dict["gas"] = await self.w3.eth.estimate_gas(tx_dict)
                signed_tx = signer.sign_transaction(tx_dict)
                signed_transactions.append(signed_tx.rawTransaction)
            else:
                raise ValueError("Unsupported transaction type in bundle")
        return signed_transactions

    def to_hex(self, signed_transaction: bytes) -> str:
        tx_hex = signed_transaction.hex()
        return tx_hex if tx_hex.startswith("0x") else "0x" + tx_hex

    def send_raw_bundle_munger(
        self,
        signed_bundled_transactions: List[HexBytes],
        target_block_number: int,
        opts: Optional[FlashbotsOpts] = None,
    ) -> List[Any]:
        if opts is None:
            opts = {}
        return [{
            "txs": [self.to_hex(tx) for tx in signed_bundled_transactions],
            "blockNumber": hex(target_block_number),
            "minTimestamp": opts.get("minTimestamp", 0),
            "maxTimestamp": opts.get("maxTimestamp", 0),
            "revertingTxHashes": opts.get("revertingTxHashes", []),
            "replacementUuid": opts.get("replacementUuid", None),
        }]

    sendBundle: Method[Callable[[Any], Any]] = Method(
        FlashbotsRPC.eth_sendBundle, mungers=[send_raw_bundle_munger]
    )
    send_bundle = sendBundle

    # Other methods (cancel, simulate, etc.) would be adapted similarly for async.
    # For brevity, only the core functions are adapted in this example.

def _parse_signed_tx(signed_tx: HexBytes) -> TxParams:
    tx_type = signed_tx[0]
    if tx_type > int("0x7f", 16):
        decoded_tx = rlp.decode(signed_tx, Transaction).as_dict()
    else:
        if tx_type == 1:
            sedes = AccessListTransaction._signed_transaction_serializer
        elif tx_type == 2:
            sedes = DynamicFeeTransaction._signed_transaction_serializer
        else:
            raise ValueError(f"Unknown transaction type: {tx_type}.")
        decoded_tx = rlp.decode(signed_tx[1:], sedes).as_dict()
    decoded_tx["from"] = Account.recover_transaction(signed_tx)
    decoded_tx = dissoc(decoded_tx, "v", "r", "s")
    return decoded_tx
