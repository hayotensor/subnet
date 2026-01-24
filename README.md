# Subnet Framework

The subnet framework is divided into two stacks:

- **the network stack**: A peer-to-peer stack for communication between peers in the same subnet using libp2p.
- **the application stack**: application level logic that runs on top of the network stack.

The subnet engine API is an internal API for communication between compartments in the same network. Designed for high availability and independent failover/restarts.

This enables the decentralized network of peers and the application stack to run independently of one another without reliance on either stack. The network and the application(s) can update and restart without affecting the other.

## Getting Started

### Prerequisites

- Python 3.10+
- `pip`

### Installation

```bash
make setup
```

## Development

- **Linting**: `make lint`
- **Formatting**: `make format`
- **Cleanup**: `make clean`
