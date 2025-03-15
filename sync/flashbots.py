"""
sync/flashbots.py

This module implements the Flashbots functionality for synchronous Web3.py.
It defines the Flashbots module that attaches additional RPC methods (such as sendBundle)
to the Web3 instance.
"""

import logging
import time
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
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.method import Method
from web3.module import Module
from web3.types import Nonce, RPCEndpoint, TxParams

from ..common.types import (
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
    A class representing a synchronous Flashbots bundle response.
    It provides methods to wait for inclusion and to retrieve receipts.
    """
    def __init__(self, w3: Web3, txs: List[HexBytes], target_block_number: int):
        self.w3 = w3
        self.bundle = [{"signed_transaction": tx, "hash": self.w3.keccak(tx)} for tx in txs]
        self.target_block_number = target_block_number

    def wait(self) -> None:
        """Wait until the target block is reached."""
        while self.w3.eth.block_number < self.target_block_number:
            time.sleep(1)

    def receipts(self) -> List[TxReceipt]:
        """Retrieve receipts for all bundle transactions."""
        self.wait()
        return [self.w3.eth.get_transaction_receipt(tx["hash"]) for tx in self.bundle]

    def bundle_hash(self) -> str:
        """Calculate the bundle hash (keccak of all tx hashes concatenated)."""
        concat_hashes = reduce(lambda a, b: a + b, [tx["hash"] for tx in self.bundle])
        return self.w3.keccak(concat_hashes)

class FlashbotsPrivateTransactionResponse:
    """
    A class representing a synchronous Flashbots private transaction response.
    """
    def __init__(self, w3: Web3, signed_tx: HexBytes, max_block_number: int):
        self.w3 = w3
        self.max_block_number = max_block_number
        self.tx = {"signed_transaction": signed_tx, "hash": self.w3.keccak(signed_tx)}

    def wait(self) -> bool:
        """Wait until the tx is mined or max block reached; return True if mined."""
        while True:
            try:
                self.w3.eth.get_transaction(self.tx["hash"])
                return True
            except TransactionNotFound:
                if self.w3.eth.block_number > self.max_block_number:
                    return False
                time.sleep(1)

    def receipt(self) -> Optional[TxReceipt]:
        """Return the receipt if mined, or None if not mined in time."""
        if self.wait():
            return self.w3.eth.get_transaction_receipt(self.tx["hash"])
        else:
            return None

class Flashbots(Module):
    """
    The Flashbots module attaches methods to the Web3 instance for sending bundles,
    cancelling bundles, simulating bundles, and more.
    """
    signed_txs: List[HexBytes]
    response: Union[FlashbotsBundleResponse, FlashbotsPrivateTransactionResponse]
    logger = logging.getLogger("flashbots")

    def sign_bundle(
        self,
        bundled_transactions: List[
            Union[FlashbotsBundleTx, FlashbotsBundleRawTx, FlashbotsBundleDictTx]
        ],
    ) -> List[HexBytes]:
        """
        Given a list of bundle transactions (signed or unsigned),
        sign any unsigned transactions and return a list of raw signed transactions.
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
                    tx_dict["nonce"] = nonces.get(signer.address, self.w3.eth.get_transaction_count(signer.address))
                nonces[signer.address] = tx_dict["nonce"] + 1
                if "gas" not in tx_dict:
                    tx_dict["gas"] = self.w3.eth.estimate_gas(tx_dict)
                signed_tx = signer.sign_transaction(tx_dict)
                signed_transactions.append(signed_tx.rawTransaction)
            elif all(key in tx for key in ["v", "r", "s"]):
                # Handle dictionary-style transaction (FlashbotsBundleDictTx)
                v, r, s = tx["v"], int(tx["r"].hex(), 16), int(tx["s"].hex(), 16)
                tx_dict = {
                    "nonce": tx["nonce"],
                    "data": HexBytes(tx["input"]),
                    "value": tx["value"],
                    "gas": tx["gas"],
                }
                if "maxFeePerGas" in tx or "maxPriorityFeePerGas" in tx:
                    assert "maxFeePerGas" in tx and "maxPriorityFeePerGas" in tx
                    tx_dict["maxFeePerGas"] = tx["maxFeePerGas"]
                    tx_dict["maxPriorityFeePerGas"] = tx["maxPriorityFeePerGas"]
                else:
                    assert "gasPrice" in tx
                    tx_dict["gasPrice"] = tx["gasPrice"]
                if tx.get("accessList"):
                    tx_dict["accessList"] = tx["accessList"]
                if tx.get("chainId"):
                    tx_dict["chainId"] = tx["chainId"]
                if tx.get("to"):
                    tx_dict["to"] = HexBytes(tx["to"])
                unsigned_tx = serializable_unsigned_transaction_from_dict(tx_dict)
                raw = encode_transaction(unsigned_tx, vrs=(v, r, s))
                assert self.w3.keccak(raw) == tx["hash"]
                signed_transactions.append(raw)
        return signed_transactions

    def to_hex(self, signed_transaction: bytes) -> str:
        """Return a hexadecimal representation of a signed transaction."""
        tx_hex = signed_transaction.hex()
        return tx_hex if tx_hex.startswith("0x") else "0x" + tx_hex

    def send_raw_bundle_munger(
        self,
        signed_bundled_transactions: List[HexBytes],
        target_block_number: int,
        opts: Optional[FlashbotsOpts] = None,
    ) -> List[Any]:
        """
        Package a raw signed bundle with target block and optional parameters.
        """
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

    sendRawBundle: Method[Callable[[Any], Any]] = Method(
        FlashbotsRPC.eth_sendBundle, mungers=[send_raw_bundle_munger]
    )
    send_raw_bundle = sendRawBundle

    def send_bundle_munger(
        self,
        bundled_transactions: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]],
        target_block_number: int,
        opts: Optional[FlashbotsOpts] = None,
    ) -> List[Any]:
        signed_txs = self.sign_bundle(bundled_transactions)
        self.response = FlashbotsBundleResponse(self.w3, signed_txs, target_block_number)
        self.logger.info(f"Sending bundle targeting block {target_block_number}")
        return self.send_raw_bundle_munger(signed_txs, target_block_number, opts)

    def raw_bundle_formatter(self, resp) -> Any:
        return lambda _: resp.response

    sendBundle: Method[Callable[[Any], Any]] = Method(
        FlashbotsRPC.eth_sendBundle,
        mungers=[send_bundle_munger],
        result_formatters=raw_bundle_formatter,
    )
    send_bundle = sendBundle

    def cancel_bundles_munger(self, replacement_uuid: str) -> List[Any]:
        return [{"replacementUuid": replacement_uuid}]

    def cancel_bundle_formatter(self, resp) -> Any:
        return lambda res: {"bundleHashes": res}

    cancelBundles: Method[Callable[[Any], Any]] = Method(
        FlashbotsRPC.eth_cancelBundle,
        mungers=[cancel_bundles_munger],
        result_formatters=cancel_bundle_formatter,
    )
    cancel_bundles = cancelBundles

    def simulate(
        self,
        bundled_transactions: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]],
        block_tag: Union[int, str] = None,
        state_block_tag: int = None,
        block_timestamp: int = None,
    ):
        block_number = self.w3.eth.block_number if block_tag is None or block_tag == "latest" else block_tag
        evm_block_number = self.w3.to_hex(block_number)
        evm_block_state_number = self.w3.to_hex(state_block_tag) if state_block_tag is not None else self.w3.to_hex(block_number - 1)
        evm_timestamp = block_timestamp if block_timestamp is not None else self.extrapolate_timestamp(block_number, self.w3.eth.block_number)
        signed_bundled_transactions = self.sign_bundle(bundled_transactions)
        self.logger.info(f"Simulating bundle on block {block_number}")
        call_result = self.call_bundle(signed_bundled_transactions, evm_block_number, evm_block_state_number, evm_timestamp)
        return {
            "bundleHash": call_result["bundleHash"],
            "coinbaseDiff": call_result["coinbaseDiff"],
            "results": call_result["results"],
            "signedBundledTransactions": signed_bundled_transactions,
            "totalGasUsed": reduce(lambda a, b: a + b["gasUsed"], call_result["results"], 0),
        }

    def extrapolate_timestamp(self, block_tag: int, latest_block_number: int):
        block_delta = block_tag - latest_block_number
        if block_delta < 0:
            raise Exception("block extrapolation negative")
        return self.w3.eth.get_block(latest_block_number)["timestamp"] + (block_delta * SECONDS_PER_BLOCK)

    def call_bundle_munger(
        self,
        signed_bundled_transactions: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]],
        evm_block_number,
        evm_block_state_number,
        evm_timestamp,
        opts: Optional[FlashbotsOpts] = None,
    ) -> Any:
        inpt = [{
            "txs": [tx.hex() for tx in signed_bundled_transactions],
            "blockNumber": evm_block_number,
            "stateBlockNumber": evm_block_state_number,
            "timestamp": evm_timestamp,
        }]
        return inpt

    call_bundle: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.eth_callBundle, mungers=[call_bundle_munger]
    )

    def get_user_stats_munger(self) -> List:
        return [{"blockNumber": hex(self.w3.eth.block_number)}]

    getUserStats: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.flashbots_getUserStats,
        mungers=[get_user_stats_munger],
    )
    get_user_stats = getUserStats

    getUserStatsV2: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.flashbots_getUserStatsV2,
        mungers=[get_user_stats_munger],
    )
    get_user_stats_v2 = getUserStatsV2

    def get_bundle_stats_munger(
        self, bundle_hash: Union[str, int], block_number: Union[str, int]
    ) -> List:
        if isinstance(bundle_hash, int):
            bundle_hash = hex(bundle_hash)
        if isinstance(block_number, int):
            block_number = hex(block_number)
        return [{"bundleHash": bundle_hash, "blockNumber": block_number}]

    getBundleStats: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.flashbots_getBundleStats,
        mungers=[get_bundle_stats_munger],
    )
    get_bundle_stats = getBundleStats

    getBundleStatsV2: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.flashbots_getBundleStatsV2,
        mungers=[get_bundle_stats_munger],
    )
    get_bundle_stats_v2 = getBundleStatsV2

    def send_private_transaction_munger(
        self,
        transaction: Union[FlashbotsBundleTx, FlashbotsBundleRawTx],
        max_block_number: Optional[int] = None,
    ) -> Any:
        if "signed_transaction" in transaction:
            signed_transaction = transaction["signed_transaction"]
        else:
            signed_transaction = transaction["signer"].sign_transaction(transaction["transaction"]).rawTransaction
        if max_block_number is None:
            current_block = self.w3.eth.block_number
            max_block_number = current_block + 25
        params = {"tx": self.to_hex(signed_transaction), "maxBlockNumber": max_block_number}
        self.response = FlashbotsPrivateTransactionResponse(self.w3, signed_transaction, max_block_number)
        self.logger.info(f"Sending private transaction with max block number {max_block_number}")
        return [params]

    sendPrivateTransaction: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.eth_sendPrivateTransaction,
        mungers=[send_private_transaction_munger],
        result_formatters=lambda resp: (lambda _: resp.response),
    )
    send_private_transaction = sendPrivateTransaction

    def cancel_private_transaction_munger(
        self,
        tx_hash: str,
    ) -> bool:
        params = {"txHash": tx_hash}
        self.logger.info(f"Cancelling private transaction with hash {tx_hash}")
        return [params]

    cancelPrivateTransaction: Method[Callable[[Any], Any]] = Method(
        json_rpc_method=FlashbotsRPC.eth_cancelPrivateTransaction,
        mungers=[lambda tx_hash: [{"txHash": tx_hash}]],
    )
    cancel_private_transaction = cancelPrivateTransaction

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
