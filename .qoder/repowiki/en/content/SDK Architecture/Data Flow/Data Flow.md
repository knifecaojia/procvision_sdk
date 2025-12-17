# Data Flow

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [spec.md](file://spec.md)
- [runner_spec.md](file://runner_spec.md)
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py)
- [procvision_algorithm_sdk/errors.py](file://procvision_algorithm_sdk/errors.py)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py)
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json)
- [tests/test_base_algo.py](file://tests/test_base_algo.py)
- [tests/test_shared_memory.py](file://tests/test_shared_memory.py)
- [tests/test_session.py](file://tests/test_session.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document explains the end-to-end data flow within the ProcVision Algorithm SDK, focusing on the algorithm execution lifecycle from initialization through runtime phases. It covers:
- Handshake protocol and heartbeat mechanism
- Step execution for pre_execute and execute
- How parameters (step_index, pid, user_params), context (session), and image data (shared_mem_id, image_meta) are passed between platform and algorithm
- Bidirectional communication via stdin/stdout with length-prefixed JSON frames and stderr for structured logging
- Sequence diagrams for normal execution, error handling, and heartbeat monitoring
- References to spec.md for payload structures and runner_spec.md for protocol timing and timeout policies

## Project Structure
The SDK is organized around a small set of cohesive modules:
- Base algorithm interface and lifecycle hooks
- Session state management
- Shared memory utilities for image transport
- Structured logging and diagnostics
- CLI for validation, local simulation, packaging, and scaffolding
- Example algorithm implementation and manifest

```mermaid
graph TB
subgraph "SDK"
base["base.py<br/>BaseAlgorithm"]
sess["session.py<br/>Session"]
shm["shared_memory.py<br/>read/write shared images"]
log["logger.py<br/>StructuredLogger"]
diag["diagnostics.py<br/>Diagnostics"]
err["errors.py<br/>Error types"]
cli["cli.py<br/>validate/run/package/init"]
end
subgraph "Algorithm Example"
ex_main["algorithm_example/main.py<br/>AlgorithmExample"]
ex_manifest["algorithm-example/manifest.json"]
end
base --> sess
base --> log
base --> diag
base --> shm
cli --> ex_main
cli --> ex_manifest
ex_main --> base
ex_main --> shm
```

**Diagram sources**
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)
- [procvision_algorithm_sdk/errors.py](file://procvision_algorithm_sdk/errors.py#L1-L14)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)

**Section sources**
- [README.md](file://README.md#L1-L116)
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)
- [procvision_algorithm_sdk/errors.py](file://procvision_algorithm_sdk/errors.py#L1-L14)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)

## Core Components
- BaseAlgorithm: Defines lifecycle hooks (setup, teardown, on_step_start, on_step_finish, reset) and abstract methods (get_info, pre_execute, execute). It also exposes logger and diagnostics helpers.
- Session: Provides a lightweight, in-memory key-value store for cross-step state sharing during a single detection session.
- Shared Memory Utilities: Provide a development-time image transport abstraction and a read helper that returns a numpy array given shared_mem_id and image_meta.
- StructuredLogger: Emits structured JSON records to stderr for logging.
- Diagnostics: Collects diagnostic metrics that can be included in algorithm responses.
- CLI: Validates algorithm packages, runs locally against images, packages offline deliverables, and initializes scaffolding.

Key data flow elements:
- Parameters: step_index, pid, user_params
- Context: session (id, context, state_store)
- Image data: shared_mem_id, image_meta (width, height, timestamp_ms, camera_id)
- Protocol: stdin/stdout frames, stderr structured logs

**Section sources**
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

## Architecture Overview
The platform and algorithm communicate over a length-prefixed JSON frame protocol on stdin/stdout, with structured logging on stderr. The Runner manages lifecycle, session creation, and step orchestration. The algorithm implements BaseAlgorithm and receives inputs via pre_execute/execute.

```mermaid
graph TB
Runner["Runner (Platform)"]
Algo["Algorithm Process (SDK)"]
Stdin["stdin<br/>length-prefixed JSON"]
Stdout["stdout<br/>length-prefixed JSON"]
Stderr["stderr<br/>structured logs"]
Runner --> Stdout
Runner <-- Stdin --> Algo
Runner --> Stderr
Algo --> Stderr
subgraph "Algorithm Lifecycle"
Setup["setup()"]
Pre["pre_execute(step_index, pid, session, user_params, shared_mem_id, image_meta)"]
Exec["execute(step_index, pid, session, user_params, shared_mem_id, image_meta)"]
Finish["on_step_finish()"]
Teardown["teardown()"]
end
Runner --> Setup
Runner --> Pre
Runner --> Exec
Runner --> Finish
Runner --> Teardown
```

**Diagram sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)

## Detailed Component Analysis

### BaseAlgorithm and Lifecycle Hooks
BaseAlgorithm defines:
- Lifecycle: setup, teardown, on_step_start, on_step_finish, reset
- Interface: get_info, pre_execute, execute
- Helpers: logger (structured), diagnostics (publish/get)

```mermaid
classDiagram
class BaseAlgorithm {
+logger
+diagnostics
+setup() void
+teardown() void
+on_step_start(step_index, session, context) void
+on_step_finish(step_index, session, result) void
+reset(session) void
+get_info() Dict
+pre_execute(step_index, pid, session, user_params, shared_mem_id, image_meta) Dict
+execute(step_index, pid, session, user_params, shared_mem_id, image_meta) Dict
}
class Session {
+id
+context
+get(key, default) Any
+set(key, value) void
+delete(key) bool
+exists(key) bool
}
class StructuredLogger {
+info(message, **fields) void
+debug(message, **fields) void
+error(message, **fields) void
}
class Diagnostics {
+publish(key, value) void
+get() Dict
}
BaseAlgorithm --> Session : "receives"
BaseAlgorithm --> StructuredLogger : "uses"
BaseAlgorithm --> Diagnostics : "uses"
```

**Diagram sources**
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)

**Section sources**
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)

### Session State Management
Session encapsulates:
- id and context (product_code, operator, trace_id)
- state_store (in-memory, JSON-serializable values)
- get/set/delete/exists APIs

```mermaid
flowchart TD
Start(["Session.set(key, value)"]) --> Validate["Validate JSON serializability"]
Validate --> |Fail| RaiseErr["Raise TypeError"]
Validate --> |Pass| Store["Store in state_store"]
Store --> End(["Done"])
Start2(["Session.get(key, default)"]) --> Lookup["Lookup in state_store"]
Lookup --> Found{"Found?"}
Found --> |Yes| ReturnVal["Return stored value"]
Found --> |No| ReturnDefault["Return default"]
ReturnVal --> End2(["Done"])
ReturnDefault --> End2
```

**Diagram sources**
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)

**Section sources**
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [tests/test_session.py](file://tests/test_session.py#L1-L24)

### Shared Memory Image Transport
The SDK provides a development-time shared memory abstraction:
- dev_write_image_to_shared_memory
- read_image_from_shared_memory returns a numpy array using image_meta (width, height, color_space optional)
- Fallback behavior if raw bytes are not a valid image

```mermaid
flowchart TD
A["read_image_from_shared_memory(shared_mem_id, image_meta)"] --> CheckWH["Validate width/height > 0"]
CheckWH --> |No| ReturnNone["Return None"]
CheckWH --> |Yes| Fetch["Fetch data by shared_mem_id"]
Fetch --> IsArray{"Is numpy array?"}
IsArray --> |Yes| Convert["Ensure 3 channels, handle BGR if requested"]
Convert --> ReturnArr["Return uint8 array"]
IsArray --> |No| TryDecode["Try decode bytes via PIL"]
TryDecode --> DecodeOK{"Decoded?"}
DecodeOK --> |Yes| ToArray["Convert to numpy array"]
ToArray --> ReturnArr
DecodeOK --> |No| ZeroFill["Return zeros(H,W,3)"]
ReturnNone --> End(["Exit"])
ZeroFill --> End
ReturnArr --> End
```

**Diagram sources**
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)

**Section sources**
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [tests/test_shared_memory.py](file://tests/test_shared_memory.py#L1-L16)

### Protocol Frames and Handshake
Protocol framing uses 4-byte big-endian length prefix plus UTF-8 JSON. The handshake and heartbeat are defined in runner_spec.md and spec.md.

```mermaid
sequenceDiagram
participant Runner as "Runner"
participant Algo as "Algorithm"
Runner->>Algo : "stdout" hello
Algo-->>Runner : "stdout" hello
Note over Runner,Algo : "Handshake complete"
loop Heartbeat
Runner->>Algo : "stdin" ping
Algo-->>Runner : "stdout" pong
end
Runner->>Algo : "stdin" call {method : pre_execute, payload : {step_index, pid, session, user_params, shared_mem_id, image_meta}}
Algo-->>Runner : "stdout" result {status, message, data}
Runner->>Algo : "stdin" call {method : execute, payload : {step_index, pid, session, user_params, shared_mem_id, image_meta}}
Algo-->>Runner : "stdout" result {status, message, data}
Runner->>Algo : "stdin" shutdown
Algo-->>Runner : "stdout" shutdown
```

**Diagram sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)

### Normal Execution Sequence
This sequence shows the typical flow for a single step (pre_execute then execute) with session and image data.

```mermaid
sequenceDiagram
participant Runner as "Runner"
participant Algo as "Algorithm"
participant SHM as "Shared Memory"
Runner->>Algo : "stdin" call {method : pre_execute, payload : {step_index, pid, session, user_params, shared_mem_id, image_meta}}
Algo->>SHM : "read_image_from_shared_memory(shared_mem_id, image_meta)"
SHM-->>Algo : "numpy array"
Algo-->>Runner : "stdout" result {status : "OK"/"ERROR", message, data}
Runner->>Algo : "stdin" call {method : execute, payload : {step_index, pid, session, user_params, shared_mem_id, image_meta}}
Algo->>SHM : "read_image_from_shared_memory(shared_mem_id, image_meta)"
SHM-->>Algo : "numpy array"
Algo-->>Runner : "stdout" result {status : "OK"/"ERROR", data : {result_status, ng_reason?, defect_rects?, position_rects?, debug}}
```

**Diagram sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)

### Error Handling Sequence
Errors can occur in pre_execute/execute or due to invalid inputs. The protocol uses status and message fields; fatal vs recoverable errors are indicated by error types.

```mermaid
sequenceDiagram
participant Runner as "Runner"
participant Algo as "Algorithm"
Runner->>Algo : "stdin" call {method : pre_execute, payload : {...}}
Algo-->>Runner : "stdout" result {status : "ERROR", message, error_code?}
Runner->>Algo : "stdin" call {method : execute, payload : {...}}
Algo-->>Runner : "stdout" result {status : "ERROR", message, error_code?}
Note over Runner,Algo : "Runner applies timeout/retry policy based on runner_spec"
```

**Diagram sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [procvision_algorithm_sdk/errors.py](file://procvision_algorithm_sdk/errors.py#L1-L14)

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [procvision_algorithm_sdk/errors.py](file://procvision_algorithm_sdk/errors.py#L1-L14)

### Heartbeat Monitoring Sequence
Runner periodically sends ping; algorithm must reply pong within grace period.

```mermaid
sequenceDiagram
participant Runner as "Runner"
participant Algo as "Algorithm"
loop Every heartbeat interval
Runner->>Algo : "stdin" ping {request_id}
alt Within grace period
Algo-->>Runner : "stdout" pong {request_id}
else Timeout
Runner->>Runner : "log warning"
alt Exceeded retries
Runner->>Runner : "terminate process"
else Retry
Runner->>Runner : "continue monitoring"
end
end
end
```

**Diagram sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)

### Local Simulation and Validation
The CLI provides:
- validate: checks manifest, entry_point, supported_pids match, smoke tests get_info, pre_execute, execute
- run: writes image to dev shared memory and simulates a single step
- package: builds offline zip with wheels and requirements
- init: scaffolds a new algorithm package

```mermaid
flowchart TD
V["validate(project)"] --> LoadMF["Load manifest.json"]
LoadMF --> ImportEP["Import entry_point class"]
ImportEP --> GetInfo["Call get_info()"]
GetInfo --> Smoke["Call on_step_start/pre_execute/execute/on_step_finish"]
Smoke --> Report["Generate report summary/checks"]
R["run(project, pid, image, params)"] --> WriteSHM["Write image to dev shared memory"]
WriteSHM --> CallPre["Call pre_execute"]
CallPre --> CallExec["Call execute"]
CallExec --> Teardown["Call teardown"]
Teardown --> Result["Return pre_execute & execute results"]
```

**Diagram sources**
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

**Section sources**
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

## Dependency Analysis
The algorithm example demonstrates the end-to-end usage of the SDK.

```mermaid
graph LR
Manifest["manifest.json"]
Main["algorithm_example/main.py"]
Base["BaseAlgorithm"]
SHM["read_image_from_shared_memory"]
Logger["logger.info/debug/error"]
Diag["diagnostics.publish/get"]
Manifest --> Main
Main --> Base
Main --> SHM
Main --> Logger
Main --> Diag
```

**Diagram sources**
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [procvision_algorithm_sdk/base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [procvision_algorithm_sdk/logger.py](file://procvision_algorithm_sdk/logger.py#L1-L24)
- [procvision_algorithm_sdk/diagnostics.py](file://procvision_algorithm_sdk/diagnostics.py#L1-L12)

**Section sources**
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)
- [tests/test_base_algo.py](file://tests/test_base_algo.py#L1-L65)

## Performance Considerations
- Image decoding: read_image_from_shared_memory decodes via PIL fallback; ensure image_meta matches actual dimensions to avoid unnecessary fallbacks.
- Logging: StructuredLogger writes to stderr; keep messages concise and avoid excessive logging in hot paths.
- Session size: Keep state_store small (<100KB) to minimize overhead.
- Diagnostics: Publish only necessary metrics; large payloads increase response sizes.
- Heartbeat: Keep heartbeat thread non-blocking; ensure pong replies are immediate.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Invalid PID: pre_execute/execute should return ERROR with appropriate message and error_code.
- Missing or empty image: read_image_from_shared_memory returns None; handle gracefully and return ERROR.
- Non-serializable session values: Session.set raises TypeError; ensure values are JSON-serializable.
- Protocol errors: Verify length-prefixed JSON frames and that only stdout emits protocol frames while stderr emits logs.
- Heartbeat timeouts: Ensure algorithm responds to ping within grace period; offload heavy work from heartbeat thread.

**Section sources**
- [procvision_algorithm_sdk/session.py](file://procvision_algorithm_sdk/session.py#L1-L36)
- [procvision_algorithm_sdk/shared_memory.py](file://procvision_algorithm_sdk/shared_memory.py#L1-L53)
- [runner_spec.md](file://runner_spec.md#L1-L283)

## Conclusion
The ProcVision Algorithm SDK defines a clear, protocol-driven lifecycle for algorithm execution. The platform and algorithm exchange structured JSON frames over stdin/stdout, with structured logging on stderr. The SDK’s BaseAlgorithm, Session, and shared memory utilities enable robust, testable implementations that align with the Runner’s heartbeat, timeout, and error-handling policies.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Payload Structures and Field Constraints
- Pre-execute payload: includes step_index, pid, session, user_params, shared_mem_id, image_meta.
- Pre-execute result: status, message, optional data (e.g., calibration_rects), optional debug.
- Execute result: status, message, data with result_status (OK/NG), optional ng_reason, defect_rects, position_rects, debug.
- Session: id, context, state_store (JSON-serializable values).
- Shared memory: image_meta minimal set (width, height, timestamp_ms, camera_id); read returns numpy array.

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec.md](file://spec.md#L1-L799)