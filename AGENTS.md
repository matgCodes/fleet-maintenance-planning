# RTA Fleet Integration Workspace

## Purpose

This workspace maps and tests the RTA Fleet APIs. Use this file to orient to
the local sources, protect live credentials and fleet data, and choose the
smallest verification step that answers the task.

Broader guidance still applies. Keep detailed API facts, domain definitions,
and executable behavior in their dedicated local sources below.

## Start Here

1. Read `CONTEXT.md` when the task depends on RTA terminology or resource
   relationships.
2. Read the relevant section of `RTA_FLEET_API_MAP.md` for endpoint, schema,
   permission, pagination, error, or documentation-gap facts.
3. Read `scripts/rta-first-call.mjs` before changing or extending the verified
   authentication and vehicle-search flow.
4. Check the live official documentation before treating a point-in-time API
   inventory as current.

Do not load the exhaustive appendix in `RTA_FLEET_API_MAP.md` unless the task
needs operation-level inventory. Start with its overview and the named endpoint
family.

## Source of Truth

- `CONTEXT.md` defines the workspace's canonical RTA vocabulary. It is a
  glossary, not a setup guide or implementation specification.
- `RTA_FLEET_API_MAP.md` is the dated, first-party-source map of the developer
  guide and live OpenAPI document. Its appendix is an inventory, not a promise
  that every Swagger operation is supported for third-party use.
- `scripts/rta-first-call.mjs` is the verified local example for Keychain-based
  authentication and a one-record vehicle search.
- The current RTA developer guide, OpenAPI document, and live API response are
  authoritative for facts that may have changed since the local map was
  researched.

When the guide, OpenAPI schema, and live response disagree, record what each
source says. Do not silently choose one as universally correct.

## Workspace Map

- `AGENTS.md` - local orientation and operating constraints.
- `CONTEXT.md` - RTA integration glossary and canonical terms.
- `RTA_FLEET_API_MAP.md` - API surfaces, domain families, schemas,
  relationships, gaps, and exhaustive operation inventory.
- `scripts/rta-first-call.mjs` - sanitized authentication and read-only search
  smoke test.

No nested instruction file is currently needed. Add one only when a subtree
develops rules that do not apply to the rest of this workspace.

## Working Agreements

- Distinguish the tenant-scoped Momentum REST API from the raw Data Extract
  API. Do not mix their hosts, versioning, permissions, or pagination models.
- Treat `tenantId`, `facilityId`, resource IDs, client ID, and API token as
  different identifiers. Use the glossary when a request says only “ID.”
- For resource lookup, prefer the corresponding search endpoint, read the
  returned resource ID, then call the detail endpoint.
- Known search endpoints may use `POST` while remaining read-only. Do not infer
  that an arbitrary `POST` is safe from its path or name.
- Start live exploration with the narrowest read-only request and a result
  limit of one. Inspect status and response shape before expanding scope.
- Do not run create, update, delete, close, reopen, post, import, upload, bulk,
  sync, or extract operations unless the user explicitly authorizes that live
  effect and the target tenant, resource, method, path, and payload purpose are
  clear.
- Do not assume routes containing `public` are anonymous or supported for
  external integrations. Verify the current contract.
- Keep observed runtime behavior separate from inferred behavior and from
  claims made only by the guide or OpenAPI document.

## Credentials and Live-Data Safety

The local scripts expect these macOS Keychain service names:

- `com.magstation.rta-fleet.tenant-id`
- `com.magstation.rta-fleet.client-id`
- `com.magstation.rta-fleet.client-secret`

Never write Keychain values or bearer tokens into workspace files, shell
history, command arguments, logs, screenshots, test fixtures, or chat output.
Retrieve them inside the process that needs them, keep tokens in memory, and
discard them when the process exits.

The documented token request places the client secret in the URL query. Never
print that URL, enable verbose HTTP logging for it, or include it in errors.

Default verification output to HTTP status, response keys, item counts, and
pagination metadata. Do not print fleet records or personally identifying data
unless the user asks for the specific data and the task requires it.

## Setup and Verification

Requirements:

- macOS with the `security` command and the three Keychain items above.
- Node.js 18 or newer for native `fetch`.

Use these checks:

```sh
node --check scripts/rta-first-call.mjs
./scripts/rta-first-call.mjs --help
./scripts/rta-first-call.mjs
```

The live smoke test authenticates and runs a one-record vehicle search. It must
not print credentials, tokens, token-request URLs, or vehicle details.

## Skill Routing

- Use `domain-modeling` when RTA terms or resource boundaries need to be added,
  renamed, or challenged; keep `CONTEXT.md` free of implementation details.
- Use `agents-md-architect` when changing this instruction hierarchy or adding
  a nested `AGENTS.md`.
- Use a first-party research workflow when refreshing the dated API map.
- Use a diagnosis workflow before changing the script when authentication or a
  previously verified read-only call fails.

## Handoff

For a paused or completed task, record only what helps the next agent resume:

- objective and current status;
- files changed;
- commands run and sanitized outcomes;
- API method and path tested;
- confirmed documentation conflicts or open questions;
- next concrete action.

Never include credentials, tokens, token-request URLs, or returned fleet-record
contents in a handoff.

## What Belongs Here

- Root-level orientation and source routing.
- Constraints that apply to every live RTA API task in this workspace.
- Stable setup and verification entry points.
- Pointers to domain, research, scripts, and future local control documents.

## What Does Not Belong Here

- Exhaustive endpoint or schema lists; keep them in `RTA_FLEET_API_MAP.md`.
- Domain definitions; keep them in `CONTEXT.md`.
- Credentials, tokens, tenant data, or live response bodies.
- One-off research notes, transient counts, session history, or subagent
  prompts.
- Detailed procedures that belong in a script, runbook, or specialized skill.
