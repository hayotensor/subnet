# Subnet Engine API

Internal engine API for communication between compartments in the same network. Designed for high availability and independent failover/restarts.

## Features

- **Decoupled Architecture**: Engine and Coordinator can start, fail, and restart independently.
- **Robust Communication**: Uses Unix Domain Sockets with MessagePack framing for efficient IPC.
- **High Availability**: Automatic reconnection logic in the Coordinator.
- **Async-first**: Built with `trio` for robust concurrency.

## Getting Started

### Prerequisites

- Python 3.10+
- `pip`

### Installation

```bash
make setup
```

### Running

Start the engine:

```bash
make run-engine
```

In another terminal, start the coordinator:

```bash
make run-coordinator
```

## Configuration

Configuration can be managed via `.env` file or `config.ini`. See `.env.example` for available options.

## Development

- **Linting**: `make lint`
- **Formatting**: `make format`
- **Cleanup**: `make clean`
