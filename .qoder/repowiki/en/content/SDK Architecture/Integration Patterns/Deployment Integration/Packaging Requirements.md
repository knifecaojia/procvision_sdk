# Packaging Requirements

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [runner_spec.md](file://runner_spec.md)
- [spec_runner.md](file://spec_runner.md)
- [cli.py](file://procvision_algorithm_sdk/cli.py)
- [base.py](file://procvision_algorithm_sdk/base.py)
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py)
- [pyproject.toml](file://pyproject.toml)
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
This document specifies the offline deployment package structure required by the ProcVision Runner and explains how to build it using the ProcVision CLI. It covers the mandatory components, the zip packaging process, validation checks, and how a typical algorithm project maps to the final package layout. It also highlights the security and reproducibility benefits of air-gapped dependency installation and provides troubleshooting guidance for common packaging errors.

## Project Structure
The offline package must include:
- Algorithm source code directory (with the entry point class referenced by manifest)
- manifest.json (defines metadata, parameters, and interface version)
- requirements.txt (pins exact dependency versions)
- wheels/ directory (pre-compiled wheel files for all dependencies)
- Optional assets/ directory (as needed)

The ProcVision Runner expects the package to be a zip archive produced by the CLI command described below. The Runner validates the package structure and installs dependencies from wheels only.

```mermaid
graph TB
A["Offline Package Zip<br/>name-vX.Y-offline.zip"] --> B["Root Directory"]
B --> C["Source Code Directory<br/>e.g., algorithm_example/"]
B --> D["manifest.json"]
B --> E["requirements.txt"]
B --> F["wheels/ (directory)"]
B --> G["assets/ (optional)"]
```

**Section sources**
- [README.md](file://README.md#L1-L116)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

## Core Components
- Algorithm source code: Implements BaseAlgorithm and exposes get_info, pre_execute, execute, plus lifecycle hooks as needed.
- manifest.json: Defines name, version, entry_point, supported_pids, and steps with parameter schemas.
- requirements.txt: Contains pinned dependency lines for exact versions.
- wheels/: Contains pre-built wheel files matching the target platform and Python ABI.
- assets/: Optional directory for auxiliary files (e.g., calibration data, models).

These components are validated by the Runner during installation and by the CLI’s validate command during development.

**Section sources**
- [README.md](file://README.md#L1-L116)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

## Architecture Overview
The packaging and validation pipeline integrates the CLI, the algorithm project, and the Runner.

```mermaid
sequenceDiagram
participant Dev as "Developer"
participant CLI as "procvision-cli"
participant FS as "File System"
participant Wheel as "pip download"
participant Zip as "Zip Archive"
participant Runner as "Runner"
Dev->>CLI : "procvision-cli package <project>"
CLI->>FS : "Read manifest.json"
CLI->>FS : "Locate requirements.txt"
alt "requirements.txt missing"
CLI->>Wheel : "pip freeze" (auto-freeze)
Wheel-->>CLI : "requirements.sanitized.txt"
end
CLI->>Wheel : "pip download -r requirements.txt -d wheels/"
Wheel-->>CLI : "wheels/*.whl"
CLI->>Zip : "Add src, manifest.json, requirements.txt, wheels/, assets/"
Zip-->>Dev : "name-vX.Y-offline.zip"
Dev->>Runner : "Install/Activate zip"
Runner->>Zip : "Open and validate structure"
Runner->>FS : "Install deps from wheels/ only"
Runner-->>Dev : "Ready to run"
```

**Diagram sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

## Detailed Component Analysis

### Offline Package Layout
- Root-level files and directories:
  - Source code directory named after the algorithm package
  - manifest.json
  - requirements.txt
  - wheels/ directory
  - assets/ directory (optional)
- The Runner will extract the package to a deployed directory and install dependencies using only the wheels inside wheels/.

```mermaid
flowchart TD
Start(["Package Build"]) --> CheckManifest["Check manifest.json exists"]
CheckManifest --> CheckReq["Check requirements.txt exists"]
CheckReq --> DownloadWheels["Download wheels matching target platform/ABI"]
DownloadWheels --> AddSrc["Add source code directory"]
AddSrc --> AddAssets["Add assets/ if present"]
AddAssets --> ZipPackage["Create offline zip"]
ZipPackage --> Validate["Runner validates structure and dependencies"]
Validate --> Install["Runner installs only from wheels/"]
Install --> Ready["Package ready for activation"]
```

**Section sources**
- [README.md](file://README.md#L1-L116)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

### Manifest.json Requirements
- Fields: name, version, entry_point, supported_pids, steps (each step defines index, name, and params)
- The Runner uses entry_point to launch the algorithm process and to validate the class implements BaseAlgorithm and returns a valid get_info structure.

```mermaid
classDiagram
class Manifest {
+string name
+string version
+string entry_point
+string[] supported_pids
+Step[] steps
}
class Step {
+int index
+string name
+Param[] params
}
class Param {
+string key
+string type
+any default
+any min
+any max
+string[] choices
+bool required
+string description
+string unit
}
Manifest --> Step : "contains"
Step --> Param : "contains"
```

**Diagram sources**
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)

**Section sources**
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)
- [runner_spec.md](file://runner_spec.md#L1-L283)

### Requirements.txt Pinning
- The CLI reads requirements.txt and sanitizes it by removing hash markers and extra pip options.
- Wheels are downloaded using the target platform, Python version, implementation, and ABI to match the Runner’s runtime environment.

```mermaid
flowchart TD
A["requirements.txt"] --> B["Sanitize lines<br/>remove #sha256= and --hash="]
B --> C["pip download -r requirements.txt -d wheels/"]
C --> D["--platform/--python-version/--implementation/--abi"]
D --> E["Only binary wheels (--only-binary=:all:)"]
```

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

### Wheels/ Directory
- Must contain all dependencies required by the algorithm.
- The Runner installs dependencies exclusively from wheels/ using a no-index approach to ensure air-gapped reproducibility.

**Section sources**
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

### Algorithm Source Code
- The example algorithm implements BaseAlgorithm and demonstrates lifecycle hooks, parameter usage, and returning structured results with result_status and optional debug fields.

```mermaid
classDiagram
class BaseAlgorithm {
+setup() void
+teardown() void
+on_step_start(step_index, session, context) void
+on_step_finish(step_index, session, result) void
+reset(session) void
+get_info() Dict
+pre_execute(...) Dict
+execute(...) Dict
}
class AlgorithmExample {
+setup() void
+teardown() void
+on_step_start(step_index, session, context) void
+on_step_finish(step_index, session, result) void
+reset(session) void
+get_info() Dict
+pre_execute(...) Dict
+execute(...) Dict
}
AlgorithmExample --|> BaseAlgorithm
```

**Diagram sources**
- [base.py](file://procvision_algorithm_sdk/base.py#L1-L58)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)

**Section sources**
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [base.py](file://procvision_algorithm_sdk/base.py#L1-L58)

### Packaging Workflow with procvision-cli package
- Command: procvision-cli package <project>
- Behavior:
  - Reads manifest.json to determine name and version
  - Locates or auto-generates requirements.txt
  - Sanitizes requirements.txt
  - Downloads wheels into wheels/ using target platform/ABI
  - Zips the project root, including wheels/ and excluding wheels/ from the source tree
  - Returns the path to the generated offline zip

```mermaid
sequenceDiagram
participant Dev as "Developer"
participant CLI as "procvision-cli package"
participant MF as "manifest.json"
participant REQ as "requirements.txt"
participant PIP as "pip download"
participant ZIP as "Zipper"
Dev->>CLI : "package <project>"
CLI->>MF : "Load name/version"
CLI->>REQ : "Find or auto-freeze"
CLI->>PIP : "Download wheels to wheels/"
PIP-->>CLI : "wheels/*.whl"
CLI->>ZIP : "Add project root + wheels/"
ZIP-->>Dev : "name-vX.Y-offline.zip"
```

**Diagram sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

### Validation Checks During Packaging and Deployment
- CLI validate checks:
  - manifest.json existence and loadability
  - required fields: name, version, entry_point, supported_pids
  - entry_point import and subclassing BaseAlgorithm
  - get_info returns a dict with steps
  - supported_pids match between manifest and get_info
  - smoke execution of pre_execute and execute
  - zip structure validation (manifest, requirements, wheels presence)
- Runner validate checks (during installation):
  - Presence of manifest.json, requirements.txt, wheels/
  - Compatibility of Python version and ABI with wheels
  - Successful installation from wheels only

```mermaid
flowchart TD
V0["CLI validate"] --> V1["manifest.json exists & loadable"]
V1 --> V2["entry_point importable and subclass BaseAlgorithm"]
V2 --> V3["get_info returns dict with steps"]
V3 --> V4["supported_pids match"]
V4 --> V5["pre_execute/execute return dicts with valid statuses"]
V5 --> V6["Optional: zip structure check"]
V6 --> V7["CLI passes"]
R0["Runner validate"] --> R1["manifest.json present"]
R1 --> R2["requirements.txt present"]
R2 --> R3["wheels/ present"]
R3 --> R4["Python/ABI compatible with wheels"]
R4 --> R5["Install from wheels only succeeds"]
R5 --> R6["Runner passes"]
```

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

### Example: algorithm-example Project Mapping
- The example algorithm demonstrates:
  - manifest.json with name, version, entry_point, supported_pids, and steps with parameters
  - AlgorithmExample class implementing BaseAlgorithm and returning structured results
- The CLI package command will:
  - Read manifest.json to determine name and version
  - Auto-generate requirements.txt if missing
  - Download wheels into wheels/
  - Zip the project root, preserving the source directory and adding wheels/

```mermaid
graph TB
M["algorithm-example/manifest.json"] --> P["procvision-cli package"]
S["algorithm_example/main.py"] --> P
P --> O["algorithm-example-v1.0-offline.zip"]
```

**Diagram sources**
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

**Section sources**
- [algorithm-example/manifest.json](file://algorithm-example/manifest.json#L1-L25)
- [algorithm-example/algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L150)
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)

## Dependency Analysis
- The CLI depends on:
  - manifest.json for metadata and entry_point
  - requirements.txt for dependency pinning
  - pip download to populate wheels/
  - zip creation to produce the offline package
- The Runner depends on:
  - manifest.json to launch the algorithm
  - wheels/ for dependency installation
  - requirements.txt to verify dependency completeness

```mermaid
graph LR
CLI["procvision-cli"] --> MAN["manifest.json"]
CLI --> REQ["requirements.txt"]
CLI --> WHL["wheels/"]
CLI --> ZIP["offline zip"]
RUN["Runner"] --> ZIP
RUN --> MAN
RUN --> WHL
```

**Diagram sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

## Performance Considerations
- Using pre-compiled wheels avoids compilation overhead during deployment.
- Air-gapped installation ensures deterministic dependency resolution and faster cold starts.
- Keeping wheels aligned with the target platform/ABI prevents runtime fallbacks and potential compatibility issues.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common packaging errors and resolutions:
- Missing wheels directory or wheels not downloaded:
  - Ensure requirements.txt exists or use --auto-freeze to generate it.
  - Verify the target platform/Python version/ABI match the wheels.
- Incorrect manifest format:
  - Confirm required fields: name, version, entry_point, supported_pids.
  - Ensure steps array contains valid param schemas.
- Excluded files in the zip:
  - The CLI excludes wheels/ from the source tree when zipping; ensure wheels/ is present and populated.
- Incompatible Python/ABI:
  - Align --python-version, --implementation, and --abi with the wheels’ metadata.
- Dependency completeness:
  - After packaging, run procvision-cli validate on the zip to confirm manifest, requirements, and wheels presence.
- Installation failures in Runner:
  - Confirm wheels/ contains all required dependencies and that Python/ABI match the target environment.

Security and reproducibility benefits:
- Air-gapped installation eliminates network exposure and ensures deterministic builds.
- Pinning exact versions in requirements.txt and using pre-compiled wheels guarantees identical environments across deployments.

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [runner_spec.md](file://runner_spec.md#L1-L283)
- [spec_runner.md](file://spec_runner.md#L1-L193)

## Conclusion
The offline deployment package for the ProcVision Runner requires a strict structure: algorithm source code, manifest.json, requirements.txt, wheels/, and optional assets/. The procvision-cli package command automates dependency downloading and packaging, while the Runner enforces validation and air-gapped installation. Following the guidelines and troubleshooting steps outlined here ensures reliable, secure, and reproducible deployments.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Appendix A: CLI Commands Overview
- procvision-cli validate: Validates manifest, entry_point, get_info, and optional zip structure.
- procvision-cli package: Builds the offline zip using manifest, requirements, and wheels/.
- procvision-cli run: Local simulation using a test image and shared memory.

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)
- [README.md](file://README.md#L1-L116)

### Appendix B: Target Environment Configuration
- The CLI can read a .procvision_env.json file in the project to set wheels platform, Python version, implementation, and ABI defaults.
- Alternatively, pass explicit arguments to the package command.

**Section sources**
- [cli.py](file://procvision_algorithm_sdk/cli.py#L1-L615)