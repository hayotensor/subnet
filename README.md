# Subnet Framework

🚧 **IN DEVELOPMENT** ☢️

The Subnet Framework is a high-performance, modular system designed for decentralized resource sharing and task execution. It utilizes a **compartmentalized architecture** where the P2P networking, application logic, and consensus loops are isolated into independent stacks.

## Architecture & Stacks

The framework is divided into three primary stacks that communicate via an internal **Engine API**:

* **Network Stack (`network/`)**: A peer-to-peer communication layer built on `libp2p`. It manages identity, peer discovery, and raw data transmission within the subnet.
* **Application Stack (`app/`)**: The application-level logic (e.g., LLM inference handlers, task processing) that runs on top of the network stack.
* **Consensus Stack (`consensus/`)**: Performs scoring, and interacts with the Hypertensor blockchain to handle consensus proposals and attestations.

## The Engine API (JSON-RPC 2.0)

Compartments communicate with each other using a streaming **JSON-RPC 2.0 over HTTP** protocol.

### Why Compartmentalize?

* **Independent Failover**: If the Application Stack restarts, the Network Stack remains alive, preventing the node from dropping out of the P2P network.
* **Real-time Updates**: You can update and restart the logic in one stack (e.g., switching/adding an LLM model in the App) without requiring a restart of the entire P2P node.
* **Language Agnostic**: Because communication is standard JSON-RPC, different stacks can eventually be written in different languages (Python, Rust, Go) while remaining interoperable.

## Getting Started

### Prerequisites

* Python 3.10+
* `pip`
* `rocksdb` (for metadata storage)

### Installation

```bash
make setup
```

## Running the Node

Testing a full node setup requires running the stacks as independent processes:

1. **Start the Engine Proxy**: Acts as the communication hub.

    ```bash
    make run-engine
    ```

2. **Start the App Server**: Handles the actual tasks.

    ```bash
    make run-app
    ```

3. **Start the Consensus Loop**: Manages scoring and blockchain sync.

    ```bash
    make run-consensus
    ```

4. **Start the Coordinator**: The entry point for the P2P network.

    ```bash
    make run-coordinator
    ```

## Development & Testing

* **Test All Suites**: `PYTHONPATH=engine/src:app/src pytest engine/tests app/tests`
* **Linting**: `make lint`
* **Formatting**: `make format`
* **Cleanup**: `make clean`