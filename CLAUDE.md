# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The ProcVision Algorithm SDK is a Python framework that enables computer vision algorithm developers to create standardized algorithms for integration with the ProcVision industrial vision platform.

- **Language**: Python >= 3.8
- **Distribution**: PyPI package (`procvision_algorithm_sdk`)
- **Architecture**: Plugin-based decoupling between platform and algorithms
- **Purpose**: Standardized CV algorithm development with offline deployment capability

## Development Commands

### Building
```bash
# Install build dependencies
pip install build pytest

# Build wheel and sdist packages
python -m build

# Install in development mode
pip install -e .
```

### Testing
```bash
# Run unit tests
pytest -q

# Validate sample algorithm package
procvision-sdk validate --project sdk_sample

# Validate custom algorithm
procvision-sdk validate --project /path/to/algorithm
```

### Version Management
- Version is defined in `pyproject.toml`
- Git tags trigger PyPI publishing (format: `v*`, e.g., `v0.1.0`)
- CI/CD automatically builds and publishes on tag push

## Architecture

### Core Component Hierarchy

```
BaseAlgorithm (abstract)
├── logger: StructuredLogger
├── diagnostics: Diagnostics
└── pid: str (algorithm instance ID)
```

**Key Methods to Implement** (`procvision_algorithm_sdk/base.py`):
- `get_info()` → Returns algorithm metadata and step definitions
- `pre_execute()` → Validates and prepares for execution
- `execute()` → Main algorithm execution logic

**Lifecycle Hooks** (optional):
- `setup()` - One-time initialization
- `teardown()` - Cleanup
- `on_step_start()` - Step begin notification
- `on_step_finish()` - Step completion notification
- `reset()` - Session state reset

### Session Management (`procvision_algorithm_sdk/session.py`)

Session provides state persistence across algorithm steps:
```python
session.set(key, value)    # Store state
session.get(key)           # Retrieve state
session.reset()            # Clear all state
```

### Shared Memory Integration

Algorithms access images through shared memory:
```python
from procvision_algorithm_sdk import read_image_from_shared_memory

img = read_image_from_shared_memory(shared_mem_id, image_meta)
# image_meta: {width: int, height: int, channels: int}
```

### CLI Validation (`procvision_algorithm_sdk/cli.py`)

The `procvision-sdk validate` command performs:
1. Manifest validation (required fields: name, version, entry_point, supported_pids)
2. Entry point import and subclass verification
3. Abstract method implementation check
4. Smoke test execution
5. IO contract validation (status, suggest_action, error_type fields)

### Error Handling (`procvision_algorithm_sdk/errors.py`)

Two error types for different failure modes:
- `RecoverableError` - Can retry or skip
- `FatalError` - Requires abort

### Return Contract

Both `pre_execute()` and `execute()` must return dictionaries with:
```python
{
    "status": "OK" | "NG" | "ERROR",
    "suggest_action": None | "retry" | "skip" | "abort",
    "error_type": None | "recoverable" | "fatal",
    # ... additional algorithm-specific fields
}
```

## Algorithm Package Structure

Algorithm delivered as ZIP containing:
```
algorithm-package/
├── manifest.json              # Algorithm metadata
├── requirements.txt           # Dependencies
├── wheels/                    # Offline dependencies
├── assets/                    # Optional models/configs
└── source_code/               # Algorithm implementation
    └── main.py                # Entry point
```

**manifest.json** fields:
- `name`: Algorithm identifier
- `version`: Semantic version
- `entry_point`: `module.class` format (e.g., `pa_sample.main:DemoAlgorithm`)
- `supported_pids`: List of supported process IDs
- Optional: `description`

**get_info() step definition schema**:
```python
{
    "index": int,                 # Step order
    "name": str,                  # Display name
    "params": [                   # User-configurable parameters
        {
            "key": str,
            "type": "float|int|rect|enum|bool",
            "default"?: any,
            "min"?: number,      # For numeric types
            "max"?: number,
            "choices"?: list,    # For enum type
            "required"?: bool
        }
    ]
}
```

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/sdk-build-and-publish.yml`):
- **Triggers**: Push to `main` branch or `v*` tag
- **Jobs**:
  1. Install dependencies
  2. Run tests + validate sample
  3. Build packages
  4. Upload artifacts
  5. Publish to PyPI (tag only, requires `PYPI_TOKEN` secret)

## Common Development Tasks

### Creating a New Algorithm
1. Inherit from `BaseAlgorithm` class
2. Implement required `get_info()`, `pre_execute()`, `execute()` methods
3. Define algorithm steps and parameters in `get_info()`
4. Create `manifest.json` with metadata
5. Run `procvision-sdk validate` to verify
6. Package with dependencies: `pip freeze > requirements.txt`
7. Download wheels for offline use

### Modifying SDK Core
1. Changes to `BaseAlgorithm` interface require version bump
2. Update abstract methods in `base.py`
3. Update CLI validation logic if needed
4. Update sample algorithm for compliance
5. Run full test suite

### Publishing New Version
1. Update version in `pyproject.toml`
2. Create git tag: `git tag v0.1.0`
3. Push tag: `git push origin v0.1.0`
4. CI/CD automatically publishes to PyPI

## Key Design Decisions

1. **Minimal Dependencies**: Only `numpy>=1.21` required to reduce platform conflicts
2. **Offline-First**: Full offline deployment support via wheels packaging
3. **Decoupled Architecture**: Platform and algorithms developed independently
4. **Standardized I/O**: Strict return contract ensures platform interoperability
5. **Session Management**: State preservation across algorithm steps in multi-stage vision pipelines
6. **Shared Memory**: Zero-copy image transfer avoiding serialization overhead
