"""
sync/__init__.py

This module injects the Flashbots module and middleware into a synchronous Web3 instance.
It is intended for projects using standard (synchronous) Web3.py 7.8.
"""

from typing import Optional, Union, cast
from eth_account.signers.local import LocalAccount
from eth_typing import URI
from web3 import Web3
from web3._utils.module import attach_modules

from .flashbots import Flashbots
from .middleware import FlashbotsMiddleware
from .provider import FlashbotProvider

DEFAULT_FLASHBOTS_RELAY = "https://relay.flashbots.net"

# Extend the Web3 class so that our injected namespace is type‐annotated.
class FlashbotsWeb3(Web3):
    flashbots: Flashbots

def flashbot(
    w3: Web3,
    signature_account: LocalAccount,
    endpoint_uri: Optional[Union[URI, str]] = None,
) -> FlashbotsWeb3:
    """
    Inject the Flashbots module and middleware into a synchronous Web3 instance.

    This method enables sending bundles via the Flashbots RPC (such as "eth_sendBundle").

    Args:
        w3: A synchronous Web3 instance.
        signature_account: The account used to sign Flashbots messages.
        endpoint_uri: The Flashbots relay endpoint URI (defaults to the official relay).

    Returns:
        The modified Web3 instance (typed as FlashbotsWeb3) with Flashbots functionality attached.

    Example:
        >>> from web3 import Web3, HTTPProvider
        >>> from eth_account import Account
        >>> w3 = Web3(HTTPProvider("https://mainnet.infura.io/v3/YOUR_PROJECT_ID"))
        >>> signer = Account.from_key("YOUR_PRIVATE_KEY")
        >>> w3 = flashbot(w3, signer)
    """
    flashbots_provider = FlashbotProvider(signature_account, endpoint_uri)
    flash_middleware = FlashbotsMiddleware(flashbots_provider)
    w3.middleware_onion.add(flash_middleware, 'Flashbot middleware')
    attach_modules(w3, {"flashbots": (Flashbots,)})
    return cast(FlashbotsWeb3, w3)
