# MCP: Playwright MCP — Agentic Automation Plan (Local LLM PoC)

---

## 1. Overview

This document describes the architecture and execution flow for an agentic web automation system built on:
- Playwright MCP for browser control
- Local LLMs for planning and decision-making
- Deterministic scaffolding to ensure reliability

The design prioritizes:
- Reactivity over rigid scripting
- Strong separation of state vs memory
- Safety and debuggability for local LLM execution

---

## 2. Agent Orchestration

### 2.1 Top-level Agent
- Entry point for user / client code.
- Receives high-level user intent.
- Maintains overall goal and execution status.
- Decides:
  - Whether a Planner is required.
  - When to re-plan, recover, or abort.
- Returns final result, partial success, or failure to the user.

---

### 2.2 Planner (Optional / Intent-level)
- Invoked only when:
  - The user instruction is long or multi-step.
  - Execution failure requires re-planning.
- Produces intent-level subgoals, not UI actions.

Planner output format:
- Ordered list of subgoals.
- Each subgoal includes explicit success criteria.

Example:
1. Reach login page (URL contains `/login`)
2. Authenticate user (dashboard visible)
3. Navigate to user creation page
4. Create user with provided data
5. Verify user creation success message

---

### 2.3 Executor (Core Reactive Loop)

The Executor is the primary runtime component.

For each subgoal:
1. Observe
   - Read the latest page snapshot.
   - Build a structured index from the snapshot.
2. Decide
   - Select the most appropriate Playwright MCP tool.
   - Fill tool arguments using the structured index.
3. Act
   - Execute the selected Playwright MCP tool.
4. Verify
   - Validate the expected outcome using assertions.
5. Recover
   - Retry, choose an alternative action, or escalate to the Planner.

Executor constraints:
- Acts only on the latest snapshot version.
- Never uses stale element references.
- Uses memory only as hints, never as ground truth.

---

## 3. Tooling

### 3.1 Tool Registry (Canonical)
- Single source of truth for all Playwright MCP tools.
- Each tool entry contains:
  - Tool name
  - JSON schema
  - Description
  - Categories / tags (navigation, input, assertion, etc.)
- Tool selection and argument filling are handled inside the Executor.
- All tool calls are JSON-schema validated.
- Automatic repair loop is applied for invalid tool calls.

---

## 4. State and Storage

### 4.1 State Store (Authoritative, In-memory)
Maintains only the current execution state:
- Raw Playwright MCP page snapshot (YAML)
- Snapshot version ID
- Structured index extracted from the snapshot:
  - Elements: {ref, role, label, name, text, visible, enabled}
  - Forms and candidate input fields
  - Available actions
- Page metadata:
  - URL
  - Title
  - Active tab / window

Rules:
- Only the latest snapshot version may be used for actions.
- Older snapshots are discarded or summarized.

---

### 4.2 Memory Store (Non-authoritative)
Used only to assist decision-making:
- Past successful element mappings
- Field name → element patterns
- Known recovery strategies
- Application-specific behaviors

Notes:
- May use lightweight vector storage.
- Never supplies element references directly.

---

## 5. Helper Utilities

### 5.1 Snapshot Processor (Critical)
- Cleans and trims raw Playwright MCP YAML output.
- Extracts and maintains the structured index.
- Removes noise and redundant data.
- Versions snapshots and produces diffs or summaries.
- Ensures snapshot size stays within local LLM context limits.

---

### 5.2 Interruption Handler
Executed before each action:
- Detects modals, banners, overlays, and popups.
- Safely dismisses blocking UI elements.
- Prevents action failures caused by transient UI interruptions.

---

## 6. Execution Flow

User
→ Top-level Agent
  → Planner (optional)
    → Executor loop
      → Observe (latest snapshot + structured index)
      → Select tool from Tool Registry
      → Execute Playwright MCP tool
      → Update State Store
      → Verify outcome
      → Recover or Re-plan if required
→ Top-level Agent
→ User

---

## 7. Local LLM Constraints and Guardrails

- No RAG over raw YAML page snapshots.
- Structured index is the primary working context.
- Tool calls must be strictly schema-valid.
- Every subgoal has explicit verification criteria.
- Recovery is a first-class behavior.
- Snapshot versioning prevents stale-reference bugs.
- Planner outputs intent, Executor handles UI reality.

---

## 8. PoC Success Criteria

- End-to-end execution of multi-step flows.
- Deterministic, debuggable behavior.
- Graceful recovery from common UI failures.
- Stable operation within local LLM context limits.
- Clear separation of planning, execution, state, and memory.

---