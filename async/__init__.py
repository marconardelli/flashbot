"""
async/__init__.py

This module injects the Flashbots module and middleware into an asynchronous Web3 instance.
It is intended for projects using AsyncWeb3 (with async HTTP providers) and is compatible with Web3.py 7.9.
"""

from typing import Optional, Union, cast
from eth_account.signers.local import LocalAccount
from eth_typing import URI
from web3 import AsyncWeb3
from web3._utils.module import attach_modules

from .flashbots import Flashbots
from .middleware import FlashbotsMiddleware
from .provider import FlashbotProvider

DEFAULT_FLASHBOTS_RELAY = "https://relay.flashbots.net"

class FlashbotsAsyncWeb3(AsyncWeb3):
    flashbots: Flashbots

def flashbot(
    w3: AsyncWeb3,
    signature_account: LocalAccount,
    endpoint_uri: Optional[Union[URI, str]] = None,
) -> FlashbotsAsyncWeb3:
    """
    Inject the Flashbots module and middleware into an AsyncWeb3 instance.

    Args:
        w3: The AsyncWeb3 instance.
        signature_account: The account used to sign Flashbots messages.
        endpoint_uri: The Flashbots relay endpoint URI.

    Returns:
        The modified AsyncWeb3 instance (typed as FlashbotsAsyncWeb3) with Flashbots functionality.
    """
    flashbots_provider = FlashbotProvider(signature_account, endpoint_uri)
    flashbots_mw = FlashbotsMiddleware(flashbots_provider)
    w3.middleware_onion.add(flashbots_mw, "Flashbot middleware")
    attach_modules(w3, {"flashbots": (Flashbots,)})
    return cast(FlashbotsAsyncWeb3, w3)
