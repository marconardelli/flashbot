# Flashbots Middleware for Web3.py 7.9 (Beta)

This repository provides a middleware for integrating **Flashbots** into your Python projects using **Web3.py version 7.9**, supporting both synchronous and asynchronous operations.

The project began as an adaptation and update of the original [Flashbots Python project](https://github.com/flashbots), modernized to be fully compatible with the latest Web3.py middleware standards.

---

## 🚀 Features

- **Compatible with Web3.py 7.9**.
- Clearly separated synchronous (`sync`) and asynchronous (`async`) implementations.
- Class-based middleware structure following the new Web3.py 7.9 guidelines.
- Ready-to-use integration for sending Flashbots bundles and private transactions.

---

## 📂 Project Structure

```
flashbots-project/
├── sync/                # Synchronous middleware
│   ├── __init__.py
│   ├── flashbots.py
│   ├── middleware.py
│   └── provider.py
│
├── async/               # Asynchronous middleware
│   ├── __init__.py
│   ├── flashbots.py
│   ├── middleware.py
│   └── provider.py
│
├── common/              # Common shared files
│   ├── constants.py
│   └── types.py
│
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## ⚙️ Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/YourUsername/flashbots-python.git
cd flashbots-python

python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

pip install -r requirements.txt
```

---

## 🚦 Usage

### Synchronous Example

```python
from web3 import Web3, HTTPProvider
from eth_account import Account
from sync import flashbot

# Initialize Web3 instance
w3 = Web3(HTTPProvider("YOUR_NODE_URL"))
signer = Account.from_key("YOUR_PRIVATE_KEY")

# Inject Flashbots functionality
w3 = flashbot(w3, signer)

# Send a bundle (example)
bundle_response = w3.flashbots.send_bundle(
    bundled_transactions=[{...}],
    target_block_number=w3.eth.block_number + 3
)
```

### Asynchronous Example

```python
import asyncio
from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account
from async import flashbot

async def main():
    w3 = AsyncWeb3(AsyncHTTPProvider("YOUR_NODE_URL"))
    signer = Account.from_key("YOUR_PRIVATE_KEY")

    # Inject Flashbots functionality
    w3 = flashbot(w3, signer)

    # Send a bundle (example)
    bundle_response = await w3.flashbots.send_bundle(
        bundled_transactions=[{...}],
        target_block_number=await w3.eth.block_number + 3
    )

asyncio.run(main())
```

---

## 📚 Dependencies

- `web3==7.9.0`
- `eth-account`
- `requests`

---

## 🤝 Contributing

Contributions, improvements, and bug reports are welcome!

1. Fork the project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## ⚠️ Disclaimer

This project started from modifying and adapting files from the [original Flashbots Python library](https://github.com/flashbots). All rights for the original concept remain with the original creators.

This software is provided as-is, with no warranty. Use at your own risk.

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
