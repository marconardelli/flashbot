"""
async/middleware.py

This module defines the asynchronous Flashbots middleware for AsyncWeb3.
It intercepts Flashbots-specific RPC calls and routes them through the Flashbots provider.
It uses the new Web3Middleware base class (compatible with Web3.py 7.9).
"""

from typing import Any, Callable
from web3 import AsyncWeb3
from web3.middleware.base import Web3Middleware
from web3.types import RPCEndpoint, RPCResponse

from .provider import FlashbotProvider

FLASHBOTS_METHODS = {
    "eth_sendBundle",
    "eth_callBundle",
    "eth_cancelBundle",
    "eth_sendPrivateTransaction",
    "eth_cancelPrivateTransaction",
    "flashbots_getBundleStats",
    "flashbots_getUserStats",
    "flashbots_getBundleStatsV2",
    "flashbots_getUserStatsV2",
}

class FlashbotsMiddleware(Web3Middleware):
    """
    An asynchronous middleware for intercepting Flashbots-specific RPC calls.
    It extends the new Web3Middleware base class.
    """
    def __init__(self, flashbots_provider: FlashbotProvider) -> None:
        self.flashbots_provider = flashbots_provider

    async def async_wrap_make_request(
        self,
        make_request: Callable[[RPCEndpoint, Any], Any]
    ) -> Callable[[RPCEndpoint, Any], RPCResponse]:
        async def middleware(method: RPCEndpoint, params: Any) -> RPCResponse:
            if method in FLASHBOTS_METHODS:
                return await self.flashbots_provider.make_request(method, params)
            else:
                return await make_request(method, params)
        return middleware
