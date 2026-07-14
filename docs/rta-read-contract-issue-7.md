# RTA supported read contract for the planned domains — Issue #7

Sanitized working write-up backing the canonical answer posted to
[issue #7](https://github.com/matgCodes/fleet-maintenance-planning/issues/7).
No tenant data, credentials, or fleet records here by design.

## Question

Which current RTA endpoints and runtime relationships can the implementation
safely rely on for **vehicles, meters, PM, work orders, repair history, and
inspections**, including known **schema, filter, pagination, permission, and
support-boundary** conflicts?

## Sources

- `RTA_FLEET_API_MAP.md` — first-party map of the developer guide + live
  OpenAPI (`/api-json`), dated 2026-07-13 (same day as this write-up, so it is
  the current pull).
- Live read-only smoke test (`scripts/rta-first-call.mjs`), run 2026-07-13:
  token HTTP 200 (`{token}`), `search-vehicles-enhanced` HTTP **201** with keys
  `items,meta`. Confirms auth + the vehicle search path work live today. (Tenant
  record counts deliberately excluded.)

---

## Bottom line first: "safe to rely on" is two-layered

**Layer A — concrete surface that exists today.** For every one of the six
domains there is at least one current read endpoint with a known response
schema (tabulated below). These are usable now against the tenant.

**Layer B — nothing is *contractually* safe until three gates are cleared.**
The public developer guide never classifies which Swagger operations are
supported for third-party integration versus internal/product-only, so the
existence of an endpoint is not a support promise. Before the implementation
depends on any endpoint below:

1. **Confirm third-party support with RTA** for the specific operations you plan
   to use. The guide exposes a broad application backend (AI, billing, kiosk,
   public-hash, internal integration, health) with no external-vs-internal
   classification. (map gap #1, checklist #1)
2. **Pin `/api-json` and diff before regenerating clients.** RTA describes the
   API as actively developed; there is no version, sunset, or changelog policy,
   and 29 operations are already marked deprecated with no replacement links.
   (map gap #9, checklist #9)
3. **Runtime-test the weak authz/response spots** — the spec cannot be trusted
   for permission or response-shape facts on the exact endpoints below (see the
   permission and schema axes).

Everything that follows is Layer A grounded, with the Layer B caveats attached
per conflict axis.

---

## Per-domain read endpoints (Layer A)

Permission column is copied verbatim from the map's appendix. **"(blank)"**
means the OpenAPI operation carries *no* permission annotation — distinct from
the literal `Requires undefined permission` string that appears on 101 other
operations. Both mean "verify authz at runtime," but they are different spec
observations.

### 1. Vehicles — solid

| Purpose | Method + path | Response | Permission |
|---|---|---|---|
| Search | `POST /asset-management/{tenantId}/vehicles/search-vehicles-enhanced` | `SearchVehiclesQueryResults` (`items: Vehicle[]`, `meta`) | (blank) |
| Read one | `GET /asset-management/{tenantId}/vehicles/{vehicleId}` | `Vehicle` | `vehicles:view` |
| History | `GET .../vehicles/{vehicleId}/history` | (undocumented) | (blank) |

Canonical field/requiredness detail is resolved in issue #2. Search → read
`items[].id` → detail is the reliable pattern. **Live-verified today.**

### 2. Meters — usable, but fragmented and mostly write-oriented

The current meter value lives on the `Vehicle` record itself; the `meters/*`
family is auxiliary. Reads:

| Purpose | Method + path | Response | Permission |
|---|---|---|---|
| Meter transactions | `POST .../vehicles/meters/vehicle-meter-transactions` | `VehicleMeterTransactionsResults` | (blank) |
| Alternate meters (per vehicle) | `GET .../vehicles/meters/{vehicleId}/alternate-meters` | `VehicleAlternateMeters` | `vehicles:view` |
| Alternate-meter descriptions | `GET .../vehicles/meters/alternate-meter-descriptions` | `array[AlternateMeter]` | (blank) |
| Meter upper bound | `GET .../vehicles/meters/{vehicleId}/upper-bound` | `VehicleMeterUpperBoundResponse` | (blank) |

Note: transaction history is retrieved via a **POST** search endpoint (read-only
despite the verb). Meter *writes* require `vehicles:updateMeter`. There is no
single "current meter" read separate from the vehicle record.

### 3. Preventive maintenance (PM) — solid, two ID axes

| Purpose | Method + path | Response | Permission |
|---|---|---|---|
| Search PM schedules | `POST .../vehicles/pm-schedules/search` | `SearchVehiclePmSchedulesQueryResults` | `pm:view` |
| PM by vehicle | `GET .../pms/{vehicleLinkId}` | `array[VehiclePmScheduleWithDueValues]` | `vehicles:view` |
| PM by id | `GET .../pms/id/{pmId}` | `VehiclePmScheduleWithDueValues` | `vehicles:view` |
| PM history | `GET .../pms/{pmId}/vehicles/{vehicleId}/history` | `array[VehicleHistory]` | `vehicles:view` |

**Relationship trap:** the per-vehicle read is keyed by `vehicleLinkId`
(the vehicle *link* number, one of the 5 required Vehicle fields per issue #2),
**not** `vehicleId`. Do not pass the resource ID where a link ID is expected.
Note also the mixed permission model: search wants `pm:view`, the detail reads
want `vehicles:view`.

### 4. Work orders — solid, but read requires `facilityId`

| Purpose | Method + path | Response | Permission |
|---|---|---|---|
| Search (enhanced) | `POST /shop-management/{tenantId}/work-orders/search-enhanced` | `SearchWorkOrderQueryResults` | (blank) |
| Read one | `GET .../work-orders/{workOrderId}` | `WorkOrder` | `workOrders:view` |
| Notes / totals / line-total-views / PO-info | `GET .../work-orders/{workOrderId}/{notes|totals|line-total-views|wo-po-info}` | resource models | `workOrders:view` |

`GET work-orders/{id}` requires a `facilityId` query param and takes optional
`includeWorkOrderLines`. **Duplicate-operationId hazard:** `searchWorkOrdersEnhanced`
is reused on `/work-orders-estimate/search-enhanced` — a different resource with
the same operationId. Client generators must disambiguate.

### 5. Repair history — single search endpoint

| Purpose | Method + path | Response | Permission |
|---|---|---|---|
| Search repair history | `POST .../vehicles/search-repair-history` | `SearchRepairHistoryQueryResults` | (blank) |

One entry point; POST search, read-only. Authz unannotated — verify at runtime.

### 6. Inspections — most fragmented; some behind product config

There is **no single inspection search**. Inspections split into three families,
and the mechanic-vehicle-inspection family sits behind an `RTAPIN configuration`
product flag (enablement, not just permission):

| Family | Read | Response | Permission |
|---|---|---|---|
| Tire | `GET .../vehicles/{vehicleId}/tire-inspections` | `array[TireInspection]` | `vehicles:view` |
| Brake | `GET /shop-management/{tenantId}/brake-inspection/{vehicleId}` | `array[BrakeInspection]` | `vehicles:view` |
| Mechanic vehicle inspection (MVI) | template/read ops under `.../mechanic-vehicle-inspection/...` | MVI models | `Requires RTAPIN configuration` + varies; one template GET is literally `Requires undefined permission` |

MVI is mostly POST/template management, gated on `RTAPIN configuration`. Do not
assume inspections are a uniform, always-available domain — feature availability
depends on tenant product configuration.

---

## Cross-cutting conflicts, by the five named axes

### Schema conflicts
- **Token response:** guide shows `{token}`; OpenAPI types it as
  `TenantIntegration`. Live run returns `{token}` (guide wins today) — trust the
  runtime, not the spec.
- **Filter `values` typing:** guide says values may be string/number/bool/null;
  several generated filter DTOs type `values` as `array[string]`. Confirm per
  endpoint before generating a strict client.
- **No component-level descriptions:** none of the ~1,579 component schemas has
  a top-level description — units, null semantics, date meanings, and
  cardinalities must be inferred or tested.
- **Placeholder drift:** guide writes `/vehicles/{id}`; OpenAPI uses
  `{vehicleId}`. Cosmetic, but generated client names follow OpenAPI.
- **`meta.sort` vs `meta.sorts`:** guide examples disagree; OpenAPI `Meta` uses
  `sorts` (array). Trust `sorts`.

### Filter conflicts
- Documented operators: `eq, neq, gt, gte, lt, lte, contains, beginsWith,
  endsWith` (+ `ASC`/`DESC`). Several OpenAPI filter DTOs leave `operator` an
  unconstrained string — do not assume the enum is enforced.
- Valid filter/sort **fields differ per resource** (endpoint-specific
  query-option DTOs). Some also expose `search` (`searchTerm`+`fields`) and
  `contextBoosts`. Validate fields against the specific endpoint schema.

### Pagination conflicts
- `Pagination` requires numeric `offset` + `limit`. OpenAPI default `limit` is
  **2000**, but the main API maximum is **undocumented** — do not assume 2000 is
  accepted; test the ceiling per endpoint.
- Response `meta` carries `totalRecords/totalPages/page/limit/offset/sorts`.
- (Separate surface) the raw Data Extract API caps `limit` at **1000** and
  paginates by `etag`, not offset — do not conflate the two models.

### Permission conflicts
- **Bearer scheme is declared but wired to zero operations** — OpenAPI cannot
  tell you which calls need auth.
- **101 operations carry `Requires undefined permission`** (a literal broken
  annotation), and several of the exact read endpoints above carry **no
  permission annotation at all** (`search-vehicles-enhanced`,
  `work-orders/search-enhanced`, `search-repair-history`,
  `vehicle-meter-transactions`, `vehicles/{id}/history`). These two states are
  distinct; both require runtime authz verification with a least-privilege key.
- Mixed permission vocabularies within one domain (e.g., PM search =`pm:view`,
  PM detail =`vehicles:view`).

### Support-boundary conflicts (the spine)
- Public guide **does not classify** stable external endpoints vs
  internal/product/public-hash endpoints — endpoint existence ≠ support.
- **29 deprecated operations**, no replacement links or sunset dates; API
  described as actively developed with no version/compatibility/changelog
  policy and a single production host (no sandbox).
- **Duplicate `operationId`s** (73 distinct, 121 extra occurrences incl.
  `searchWorkOrdersEnhanced`) break naive client generation.
- **Error contract is weak:** 1,306 of 1,630 operations expose only a blank
  `default` response; no reusable response catalog; 429 exists only in prose
  (no `Retry-After` guarantee).

---

## Recommendation for the implementation

Rely on the Layer-A endpoints above for the six domains, but treat each as
*provisional* until the three Layer-B gates clear. Concretely:
1. Get RTA to confirm third-party support for this exact endpoint set.
2. Pin the current `/api-json`, diff on every RTA change, regenerate only the
   six-domain slice (not the full 1,579-schema document).
3. Runtime-probe authz + response shape for every (blank)/undefined-permission
   read before trusting it; use a least-privilege key (do **not** grant
   `api:extractTable` for these operational reads).
4. Handle the relationship traps: `vehicleLinkId` vs `vehicleId` for PM,
   required `facilityId` on work-order reads, POST-but-read-only searches, and
   `RTAPIN configuration`-gated inspections.
