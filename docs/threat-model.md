# Threat model — tool-using LLM application

**Scope:** Local prototype with a mock agent, simulated tools, and synthetic multi-tenant records.  
**Untrusted component:** The agent that proposes tool calls. Identity comes from the authenticated application principal, not from the model.

## Assets

- Tenant-isolated records and ownership metadata
- Role grants and permission changes
- High-risk operations: delete, export, change permissions
- Audit trail of allow/deny decisions

## Adversary goals

Cause a tool execution that violates tenant isolation, ownership, role allow-lists, or approval requirements.

## Threat catalogue

| Threat id | Description | Expected gateway effect |
| --- | --- | --- |
| `cross_tenant` | Read or mutate a record (or tenant-scoped list) belonging to another tenant | DENY (`tenant`) |
| `prohibited_tool` | Call a tool outside the principal's role allow-list | DENY (`actions`) |
| `ownership_mismatch` | Create, update, or delete a record the principal does not own. Applies to every role, including admin | DENY (`ownership`) |
| `missing_context` | Principal lacks usable identity | DENY (`context`) — covered by policy unit tests; Case JSON cannot encode empty ids because Stage 0 validation rejects them |
| `approval_missing` | High-risk tool without a matching approval token, or with a token that was already used | DENY (`approval`) |
| `malformed_tool` | Tool call carries unexpected argument keys | DENY (`schema`) |

## Out of scope

- Detecting or stopping all prompt injection
- Paid LLM APIs and live business systems
- Foundation-model training

Prompt injection may still change what the agent proposes. The gateway only evaluates the resulting `ToolCall`.
