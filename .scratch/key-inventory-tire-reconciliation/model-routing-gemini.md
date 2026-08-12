# Gemini Model Routing: Remaining Key Inventory Tire Reconciliation

Status: ready-for-orchestrator
Date: 2026-08-12

Advisory routing for the remaining GitHub issues #17 and #18, optimized for
Gemini models, reasoning effort, independent review, and selective context
caching. The bundled Gemini catalog was cached 2026-08-03, so no live refresh
was needed.

Source snapshot:

- https://ai.google.dev/pricing
- https://cloud.google.com/vertex-ai/generative-ai/docs/model-garden/introduce-models
- https://ai.google.dev/gemini-api/docs
- https://ai.google.dev/gemini-api/docs/caching

| Issue | Task | Model | Reasoning Effort | agy Identifier | Cache-Eligible | Rationale | Blockers |
|---|---|---|---|---|---|---|---|
| [#17](https://github.com/matgCodes/fleet-maintenance-planning/issues/17) | Generate the staged master copy with reconciled tire fields | `Gemini 3.6 Flash` (`gemini-3.6-flash`) | `High` | `gemini-3.6-flash-high` | Yes — immutable issue, manifest, tests, instructions, and workbook-structure summaries | #16 has frozen the 444-row manifest and all identity decisions, so #17 is bounded workbook construction with explicit row classes, output columns, style rules, source-preservation gates, and reload checks. Flash at High is the cost-effective owner, but it must consume the manifest literally and may not reclassify assets. | #16 must be closed after its checked acceptance criteria and completion comments; it is currently still open |
| [#18](https://github.com/matgCodes/fleet-maintenance-planning/issues/18) | Validate and publish the final tire-size master workbook | `Gemini 3.1 Pro` (`gemini-3.1-pro`) | `High` | `gemini-3.1-pro-high` | Yes — fresh cache or fresh source load; do not inherit #17's conclusions | This is the high-stakes persistence boundary: it independently proves source preservation, exact category and completeness totals, formulas, styles, workbook structure, and rendered output before creating the shared OneDrive artifact and updating GitHub. Pro at High is appropriate because a false pass can publish silent workbook corruption, and the reviewer must integrate structural, visual, tracker, and filesystem evidence without confirmation bias from #17. | #17 closed, all acceptance boxes checked, staged SHA-256 and completion-evidence comment present |

## Strategic Execution Rules

### 1. Context Caching Plan

Use caching only if the reusable text payload reaches Gemini's 32,768-token
threshold. For #17, a cache may contain the approved issue body, AGENTS.md,
CONTEXT.md, the frozen reconciliation manifest, its tests, and sanitized
workbook-structure/style summaries. Do not cache credentials, tokens, VINs, raw
RTA records, or private workbook contents that are unnecessary for execution.

Run #18 in a fresh Pro session. It may use a newly built cache of immutable
sources and #17's staged-workbook evidence, but must reload the staged workbook,
source hashes, GitHub state, and validation inputs itself. It must not reuse
#17's unverified conclusions as facts. If the reusable payload stays below the
cache threshold, skip caching; the two-issue chain is too short to justify cache
storage solely for cost savings.

### 2. Default Rule

Use Gemini 3.6 Flash at High effort for #17 because the upstream manifest fixes
semantics and the remaining work is bounded, testable artifact generation. Give
High reasoning and generous output headroom so preservation checks, category
handling, staging, and reload verification complete in one owner run.

### 3. Escalation Rule

Escalate #17 to Gemini 3.1 Pro at High effort if it attempts to infer identity,
cannot preserve workbook objects, sees manifest/source drift, or fails staged
reload and fixture checks. Keep #18 on Gemini 3.1 Pro at High effort; restart it
with a fresh source load if hashes, tracker state, category totals, formulas, or
rendered output disagree. Stop rather than weakening a fail-closed gate. Do not
publish while #17 is open or its completion evidence is incomplete.

### 4. Cost/Latency Optimization Note

Gemini 3.6 Flash is the economical owner for the formatting-heavy #17 after the
manifest contract is frozen. Gemini 3.5 Flash-Lite at Low effort may inventory
styles, enumerate rendered pages, or perform other deterministic sidecar checks,
but it must never own row classification, source-preservation decisions,
workbook persistence, publication, acceptance-box edits, completion comments,
or issue closure. Pro is reserved for #18's independent publication decision.

## Execution Order and Tracker Gate

1. #16 currently has all acceptance boxes checked and completion-evidence
   comments, but it remains open. Close #16 only after confirming its evidence;
   until then, #17 is blocked.
2. Run #17 in a fresh `gemini-3.6-flash-high` owner session.
3. Before #17 closes, check every verified acceptance box and add the required
   sanitized completion comment with the staged workbook and SHA-256.
4. Start #18 only after #17 is closed and its tracker gate is complete.
5. Run #18 in a fresh, independent `gemini-3.1-pro-high` owner session. After
   independent validation and publication, check its acceptance boxes, add the
   final sanitized evidence comment, and then close it.

Model routing is advisory. The issue bodies, blocker chain, tests, source gates,
and human review remain authoritative.
