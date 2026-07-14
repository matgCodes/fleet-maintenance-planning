# Decisions

Project decisions that are not derivable from the code or API map. Sanitized —
no tenant data, credentials, or fleet records. Newest first.

## 2026-07-14 — Canonical municipal vehicle record (issue #2)

**Context:** Issue #2 asked which fields/relationships form the authoritative
municipal vehicle record and how they classify (required / conditional / derived
/ explicitly-unused) per in-scope vehicle category. The terms "municipal" and
"in-scope vehicle category" were absent from the sanitized workspace.

**Decisions:**

1. **In-scope vehicle category axis = RTA `VehicleClass`** — not `Department`,
   `weightClass`, `Region`, or the Equipment/Vehicle split.
2. **Municipal scope = the entire tenant.** All vehicles are in-scope; no
   facility- or department-level sub-filtering.
3. **Answer classification is grounded in first-party live sources** — the live
   OpenAPI schema plus one read-only sampled record shape — not inferred from the
   dated API map alone. Read-only calls only; no fleet records or PII inspected.
4. **Tenant-specific detail stays off-repo.** Class labels/IDs and the full
   class-by-class matrix live in `local-reference/` (gitignored). Only sanitized
   aggregates are published (issue #2 comments, committed docs).

**Consequence (finding):** Core-record requiredness does **not** vary by
category — the five schema-required fields hold for all 284 tenant
VehicleClasses. The only genuine per-category dimension is which of the 22
user-definable slots (`value01`–`value22`) each class activates/types, plus
sparse class-level planning defaults.

**Status:** Issue #2 answered (two sanitized comments) and closed as completed.
Full write-up kept locally in `docs/vehicle-record-field-inventory.md`
(gitignored).
