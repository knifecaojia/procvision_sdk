# Handshake Protocol

<cite>
**Referenced Files in This Document**   
- [spec.md](file://spec.md)
- [runner_spec.md](file://runner_spec.md)
- [algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Handshake Protocol Overview](#handshake-protocol-overview)
3. [Hello Message Schema](#hello-message-schema)
4. [Handshake Sequence](#handshake-sequence)
5. [Timing Constraints](#timing-constraints)
6. [Error Conditions](#error-conditions)
7. [Sequence Diagram](#sequence-diagram)
8. [Process Termination](#process-termination)
9. [Implementation Details](#implementation-details)

## Introduction
The handshake protocol establishes a communication channel between the ProcVision Algorithm SDK and the host platform's Runner. This protocol ensures compatibility and readiness before any business messages are exchanged. The handshake begins when the algorithm process starts and writes a hello message to stdout, and completes when the Runner responds with its own hello message. This document details the complete handshake protocol, including message formats, timing requirements, error conditions, and consequences of handshake failure.

## Handshake Protocol Overview
The handshake protocol is the initial communication sequence between the ProcVision Algorithm SDK and the host platform's Runner. It serves as a compatibility check and connection establishment mechanism before any business logic can be executed. The protocol follows a strict sequence: the algorithm process must first send a hello message containing its SDK version, and the Runner must respond with its own hello message containing the Runner version. Only after this two-way handshake is completed can the Runner send call messages and the algorithm process begin processing business logic. This protocol ensures that both components are compatible and ready for communication, preventing version mismatches and ensuring protocol consistency.

**Section sources**
- [spec.md](file://spec.md#L615-L633)
- [runner_spec.md](file://runner_spec.md#L29-L35)

## Hello Message Schema
The hello message follows a specific JSON schema with two required fields. The message type is always "hello", and the message includes version information specific to the sender. For the algorithm SDK, the field is "sdk_version", while for the Runner, the field is "runner_version". Both messages share the same basic structure but contain version information relevant to their respective components.

The JSON schema for hello messages is defined as:

```json
{
  "type": "hello",
  "sdk_version": "x.x"  // For algorithm SDK
}
```

```json
{
  "type": "hello",
  "runner_version": "x.x"  // For Runner
}
```

The "type" field is a string literal with the value "hello" for both messages. The version field contains a semantic version string in the format "x.x" or "x.x.x" that identifies the specific version of the component. The version information allows both sides to verify compatibility and potentially handle backward compatibility if needed.

**Section sources**
- [spec.md](file://spec.md#L615-L633)
- [runner_spec.md](file://runner_spec.md#L33-L35)

## Handshake Sequence
The handshake sequence follows a strict two-step process that must be completed before any business messages can be exchanged. The sequence begins immediately after the algorithm process is started by the Runner.

First, the algorithm process, upon successful initialization, writes a hello message to stdout in the format {"type":"hello","sdk_version":"x.x"}. This message indicates that the algorithm SDK has been successfully loaded and is ready to establish communication. The message is sent to stdout using the standard output stream, as all protocol messages must be transmitted through stdout to avoid protocol stream contamination.

Second, upon receiving the hello message from the algorithm process, the Runner must respond with its own hello message in the format {"type":"hello","runner_version":"x.x"}. This response confirms that the Runner has received the algorithm's hello message and acknowledges the connection. The handshake is considered complete only after the algorithm process has received the Runner's hello message.

Until this two-way handshake is completed, no business messages (such as call or result messages) may be exchanged between the components. Any attempt to send business messages before the handshake completes will result in protocol errors and potential process termination.

**Section sources**
- [spec.md](file://spec.md#L615-L633)
- [runner_spec.md](file://runner_spec.md#L33-L35)

## Timing Constraints
The handshake protocol is subject to specific timing constraints that ensure timely connection establishment and prevent indefinite waiting. The most critical constraint is the 2-second response window for the Runner to respond to the algorithm's hello message.

After the algorithm process sends its hello message to stdout, the Runner must respond with its own hello message within 2 seconds. This timeout period is designed to be sufficient for normal system operations while preventing the algorithm process from hanging indefinitely if the Runner fails to respond. The 2-second window accounts for typical system startup times, process initialization, and network or inter-process communication latency.

If the Runner fails to respond within this 2-second window, the handshake is considered failed, and the algorithm process will be terminated. This timeout mechanism ensures system stability by preventing orphaned processes from consuming resources indefinitely. The algorithm process may implement internal timeouts to detect the absence of the Runner's response, but the ultimate responsibility for enforcing the timeout lies with the Runner's monitoring system.

**Section sources**
- [spec.md](file://spec.md#L639-L678)
- [runner_spec.md](file://runner_spec.md#L40-L42)

## Error Conditions
Several error conditions can occur during the handshake process, each with specific consequences for the algorithm process. These errors include missing hello messages, malformed hello messages, and timeout conditions.

A missing hello message occurs when the algorithm process fails to write the required {"type":"hello","sdk_version":"x.x"} message to stdout during startup. This could be due to initialization failures, exceptions during startup, or incorrect implementation of the algorithm's entry point. When the Runner does not receive this message, it cannot proceed with the handshake and will terminate the algorithm process.

A malformed hello message occurs when the message sent to stdout does not conform to the expected JSON schema. This includes syntax errors in the JSON, missing required fields, incorrect field names, or invalid data types. For example, sending {"type":"hello"} without the sdk_version field, or {"type":"hello","version":"1.0"} with an incorrect field name, would be considered malformed. The Runner validates the message structure and will reject any message that does not exactly match the expected schema.

Other error conditions include sending the hello message to the wrong output stream (such as stderr instead of stdout), sending additional messages before the handshake completes, or sending the hello message after the 2-second window has expired. All of these conditions violate the handshake protocol and will result in handshake failure and process termination.

**Section sources**
- [spec.md](file://spec.md#L634-L637)
- [runner_spec.md](file://runner_spec.md#L38-L42)

## Sequence Diagram
The following sequence diagram illustrates the complete handshake flow between the ProcVision Algorithm SDK and the host platform's Runner, including the successful handshake completion and the error path for timeout conditions.

```mermaid
sequenceDiagram
participant Algorithm as Algorithm Process
participant Runner as Runner
Algorithm->>Runner : {"type" : "hello","sdk_version" : "1.0"}
activate Runner
alt Handshake Success
Runner->>Algorithm : {"type" : "hello","runner_version" : "1.0"}
deactivate Runner
activate Algorithm
Note over Algorithm,Runner : Handshake Complete
Runner->>Algorithm : {"type" : "call",...}
Algorithm->>Runner : {"type" : "result",...}
deactivate Algorithm
else Handshake Timeout
Note over Runner : 2-second timeout
Runner->>Algorithm : Process Termination
deactivate Runner
end
```

**Diagram sources**
- [spec.md](file://spec.md#L615-L633)
- [runner_spec.md](file://runner_spec.md#L33-L35)

## Process Termination
Failure to complete the handshake protocol results in immediate termination of the algorithm process. This termination is a critical safety mechanism that prevents incompatible or malfunctioning algorithm processes from consuming system resources or causing unpredictable behavior.

When the handshake fails due to any of the error conditions described above, the Runner will terminate the algorithm process. This termination can occur through various mechanisms, including sending a SIGTERM signal for graceful shutdown or a SIGKILL signal for immediate termination if the process does not respond to graceful shutdown requests.

The process termination serves multiple purposes: it frees up system resources such as memory and CPU, prevents the accumulation of orphaned processes, and signals to the monitoring system that the algorithm failed to initialize properly. After termination, the Runner may attempt to restart the algorithm process according to its restart policy, typically allowing a limited number of restart attempts before entering a failed state that requires manual intervention.

The algorithm process should be designed to handle termination gracefully by implementing the teardown method to release any allocated resources, close open files or network connections, and perform any necessary cleanup operations. However, since handshake failure occurs very early in the process lifecycle, there are typically few resources to clean up at this stage.

**Section sources**
- [spec.md](file://spec.md#L639-L678)
- [runner_spec.md](file://runner_spec.md#L80-L85)

## Implementation Details
The handshake protocol implementation is integrated into the ProcVision Algorithm SDK and the host platform's Runner. In the SDK, the hello message is automatically generated by the framework when the algorithm process starts, provided that the algorithm is correctly implemented and the entry point is properly configured in the manifest.json file.

The algorithm's entry point, specified in the manifest.json file's "entry_point" field, determines how the algorithm class is instantiated and started. When the Runner launches the algorithm process, it uses this entry point to create an instance of the algorithm class, which triggers the initialization sequence that culminates in the hello message being sent to stdout.

The Runner's implementation includes a monitoring system that listens for the hello message from the algorithm process and validates its structure before responding with its own hello message. This monitoring system also enforces the 2-second timeout constraint, tracking the time between when the algorithm process is started and when the hello message is received.

Both the SDK and Runner are designed to handle edge cases such as malformed JSON, incorrect message types, and protocol violations, ensuring robust communication even in error conditions. The strict separation of protocol messages (on stdout) and logging output (on stderr) prevents protocol stream contamination and ensures reliable message parsing.

**Section sources**
- [spec.md](file://spec.md#L615-L633)
- [runner_spec.md](file://runner_spec.md#L29-L42)
- [algorithm_example/main.py](file://algorithm-example/algorithm_example/main.py#L1-L33)
- [procvision_algorithm_sdk/cli.py](file://procvision_algorithm_sdk/cli.py#L22-L66)