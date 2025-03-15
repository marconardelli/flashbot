"""
sync/provider.py

This module defines the FlashbotProvider for synchronous calls.
It extends Web3’s HTTPProvider to automatically add the Flashbots signature header.
"""

import logging
import os
from typing import Any, Dict, Optional, Union

from eth_account import Account, messages
from eth_account.signers.local import LocalAccount
from eth_typing import URI
from web3 import HTTPProvider, Web3
from web3.types import RPCEndpoint, RPCResponse

def get_default_endpoint() -> URI:
    return URI(os.environ.get("FLASHBOTS_HTTP_PROVIDER_URI", "https://relay.flashbots.net"))

class FlashbotProvider(HTTPProvider):
    """
    A custom HTTPProvider for Flashbots.
    
    It automatically signs requests with the required 'X-Flashbots-Signature' header.
    """
    logger = logging.getLogger("web3.providers.FlashbotProvider")

    def __init__(
        self,
        signature_account: LocalAccount,
        endpoint_uri: Optional[Union[URI, str]] = None,
        request_kwargs: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
    ):
        _endpoint_uri = endpoint_uri or get_default_endpoint()
        super().__init__(_endpoint_uri, request_kwargs, session)
        self.signature_account = signature_account

    def _get_flashbots_headers(self, request_data: bytes) -> Dict[str, str]:
        request_text = request_data.decode("utf-8")
        from web3 import Web3  # local import
        message = messages.encode_defunct(text=Web3.keccak(text=request_text).hex())
        signed_message = Account.sign_message(message, private_key=self.signature_account._private_key)
        return {
            "X-Flashbots-Signature": f"{self.signature_account.address}:{signed_message.signature.hex()}"
        }

    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(f"Making HTTP request. URI: {self.endpoint_uri}, Method: {method}")
        request_data = self.encode_rpc_request(method, params)
        combined_headers = self.get_request_headers() | self._get_flashbots_headers(request_data)
        response = self.session.request(
            method="POST",
            url=self.endpoint_uri,
            data=request_data,
            headers=combined_headers,
            **(self.request_kwargs or {})
        )
        raw_response = response.content
        decoded_response = self.decode_rpc_response(raw_response)
        self.logger.debug(f"Response received. Method: {method}, Response: {decoded_response}")
        return decoded_response
