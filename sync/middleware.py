"""
sync/middleware.py

This module defines the synchronous Flashbots middleware compatible with Web3.py 7.9.
It intercepts Flashbots-specific RPC calls (e.g. "eth_sendBundle", "eth_callBundle", etc.)
and routes them to a FlashbotProvider instance for handling.
"""

from typing import Any, Callable
from web3 import Web3
from web3.middleware.base import Web3Middleware
from web3.types import RPCEndpoint, RPCResponse

from .provider import FlashbotProvider

# Define the set of RPC methods that belong to Flashbots.
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
    Synchronous Flashbots middleware for Web3.py 7.9.
    
    This middleware intercepts RPC calls that are specific to Flashbots.
    If the RPC method is one of FLASHBOTS_METHODS, the call is forwarded
    to the FlashbotProvider (which takes care of signing and sending the request
    to the Flashbots relay). Otherwise, the call is passed through to the next layer.
    """
    def __init__(self, flashbots_provider: FlashbotProvider) -> None:
        self.flashbots_provider = flashbots_provider

    def __call__(self, w3: Web3) -> "FlashbotsMiddleware":
        # Make the middleware callable by simply returning itself.
        return self

    def wrap_make_request(
        self, make_request: Callable[[RPCEndpoint, Any], RPCResponse]
    ) -> Callable[[RPCEndpoint, Any], RPCResponse]:
        def middleware(method: RPCEndpoint, params: Any) -> RPCResponse:
            if method in FLASHBOTS_METHODS:
                # Forward Flashbots-specific calls to the FlashbotProvider.
                return self.flashbots_provider.make_request(method, params)
            else:
                # Otherwise, call the next middleware / provider.
                return make_request(method, params)
        return middleware
