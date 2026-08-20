# SPIKE — RTA Fleet API: Asset Lookup & Service Request Ingestion

**Status:** Complete (desk research)
**Date:** 2026-08-20
**Primary sources used:**
- `RTA_FLEET_API_MAP.md` (this repo) — verified map of the live RTA Momentum OpenAPI (1,340 paths / 1,630 operations / 1,579 schemas as pinned 2026-07-13), cross-checked against the RTA developer guide and API-keys manual.
- `scripts/rta-first-call.mjs` (this repo) — a **working, authenticated** read call against production, which settles the auth-flow question empirically.
- Prior research: closed issue [#7 — Verify the supported RTA read contract](https://github.com/matgCodes/fleet-maintenance-planning/issues/7).

**Currency caveat:** The OpenAPI snapshot is ~5 weeks old. Every endpoint below is *provisional until RTA confirms it is supported for third-party integrations*. Re-pin and diff `https://api.momentum-prd.rtafleet.com/api-json` before generating a client (carried forward from issue #7).

---

## TL;DR — feasibility verdict

Integration is **feasible** for all three target flows. Key corrections to the ticket's stated assumptions:

| Ticket assumption | Reality (verified) |
|---|---|
| "OAuth 2.0 / JWT token flow" | **Not standards-compliant OAuth 2.0.** It's a proprietary client-credential exchange: `GET …/get-api-token?clientId=…&clientSecret=…` returning a JWT bearer token. No `grant_type`, no `/token` POST, no refresh-token flow. |
| "permission scopes e.g. `vehicles:view`, `work-orders:create`" | Correct shape (`resource:action`), but exact strings differ. Service requests use `serviceRequests:access` / `:createWO` / `:close` / `:schedule`. Vehicle read is `vehicles:view`. |
| `/asset-management/search-vehicles-enhanced` | Real, but path is tenant-scoped: `POST /asset-management/{tenantId}/vehicles/search-vehicles-enhanced`. |
| `/service-request/public/{hash}` | Real family, corrected name: `POST /service-requests-public/{hash}/submit-service-request`. |
| "does an authenticated REST endpoint exist for service-request creation?" | **Yes.** `POST /shop-management/{tenantId}/service-requests` (`CreateServiceRequestDto` → `ServiceRequest`, perm `serviceRequests:access`). |
| `/v0/extract/` Data Extract API | Correct: `GET https://api.rtafleet.com/v0/extract/<table>?etag=…&limit=…`, perm `api:extractTable`. |
| "real-time webhook subscriptions" | **None documented.** No webhook/callback mechanism in the reviewed sources. Polling only. |

**Recommendation (short):** Use **direct REST** for asset lookup and service-request ingestion (write path). Use the **Data Extract API** only for a nightly/periodic local vehicle-directory cache. Do **not** rely on webhooks — poll `service-requests/search` for status changes. See §5.

---

## 1. Authentication & Access Control

### 1.1 Token flow (empirically verified)
`scripts/rta-first-call.mjs` performs the real exchange against production:

```
GET https://api.momentum-prd.rtafleet.com/information-management/{tenantId}/integrations/get-api-token?clientId={clientId}&clientSecret={clientSecret}
→ 200 { "token": "<JWT>" }
```
Then every subsequent call carries `Authorization: Bearer <JWT>`.

- **Not OAuth 2.0.** Despite the JWT, there is no OAuth grant, no token endpoint POST body, no refresh token. It is an RTA-proprietary key-exchange. `clientId`/`clientSecret` are RTA "API key" credentials created by an Admin-role user in Fleet360; `tenantId` is the account serial number.
- **`bearerFormat: JWT`** is declared in OpenAPI, but the spec applies **no** operation-level `security` requirement. Follow the prose guide (bearer required) — do not read the missing bindings as anonymous access.

### 1.2 Permission scopes (resource:action)
403 is returned when a required permission is absent. Confirmed relevant scopes:

| Action | Permission |
|---|---|
| Vehicle search / read | `vehicles:view` |
| Vehicle status update | `vehicles:updateStatus`, `vehicles:update` |
| Service request create / read / update | `serviceRequests:access` |
| Assign service request → work order | `serviceRequests:createWO` |
| Close service request | `serviceRequests:close` |
| Schedule service request | `serviceRequests:schedule` |
| Raw data extract (all tables) | `api:extractTable` |

> **Caution:** ~101 operations in the pinned spec declare `Requires undefined permission`. Do not guess grants for those — confirm with RTA. Provision **least-privilege** keys per integration.

### 1.3 Rate limits, expiry, quotas — **largely undocumented**
- **Token lifetime / refresh / rotation / revocation: not documented.** Build the client to re-request a token on `401` rather than assuming a TTL.
- **Rate limits:** only the existence of **HTTP 429** is documented. No published quota, burst rule, key/IP/tenant scope, `Retry-After` guarantee, or backoff recommendation. The OpenAPI does not even declare a 429 response. → Implement conservative client-side throttling + exponential backoff on 429; treat limits as unknown.
- **Concurrent request quotas: not documented.**
- **Security note:** the secret travels as a **GET query string**. Never log full token-request URLs; ensure proxies/intermediaries don't retain query strings.

---

## 2. Asset & Facility Queries

### 2.1 Enhanced vehicle search
`POST /asset-management/{tenantId}/vehicles/search-vehicles-enhanced`
Body `SearchVehiclesEnhancedDto` → `SearchVehiclesQueryResults` (`items: Vehicle[]`, `meta: Meta`). Perm `vehicles:view`.

```json
{
  "queryOptions": {
    "pagination": { "offset": 0, "limit": 50 },
    "filters": [
      { "name": "vehicleNumber", "operator": "eq", "values": ["1001"] }
    ],
    "sorts": [
      { "sortBy": "vehicleNumber", "sortOrder": "ASC" }
    ]
  }
}
```

- **Filter operators (documented, full set):** `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `contains`, `beginsWith`, `endsWith`. (Ticket named a subset.)
- **Sorting:** `ASC` / `DESC` on a `sortBy` field.
- **Pagination:** `offset` + `limit`. `Pagination.limit` has OpenAPI default `2000`; the **main-API maximum is not documented** — probe before assuming large pages.
- **Free-text search:** some query-option schemas also expose `search` (`searchTerm` + `fields[]`).
- **Response IDs:** workflow is search → read `items[].id` (UUIDs) → detail/update/delete.

**Filter-DTO caveat:** the guide says filter `values` may be string/number/bool/null, but several generated DTOs type `values` as `string[]` and leave `operator` as an unconstrained string. Confirm the exact endpoint's DTO before generating a strict typed client.

### 2.2 Facility filtering
`facilityId` is a common secondary path/query key across shop, fuel, work-order, inventory, and user operations. For vehicle search, facility scoping is expressed as a `filters[]` entry (e.g. filter on the vehicle's facility field) rather than a separate path segment. Confirm the exact filterable field name against the `Vehicle` schema.

### 2.3 [Inference item] Inactive / out-of-service assets — filter at query level vs app logic
**Answer: filterable at query level (with one confirmation).** RTA models vehicle status as a first-class `VehicleStatusCode` entity:
- `GET /asset-management/{tenantId}/vehicles/vehicle-statuses` → `VehicleStatusCode[]` (enumerate the codes, incl. active vs out-of-service).
- Vehicle status is set via `PUT /asset-management/{tenantId}/vehicles/{vehicleId}/status`.

Because the vehicle carries a status field and search accepts arbitrary `filters[]`, you can filter to active-only at the query level (e.g. `{ "name": "<statusField>", "operator": "neq", "values": ["<OOS code>"] }`). **Confirm the exact filterable field name** on the `Vehicle`/`FetchVehicleQueryOptionsDto` schema (or via a one-shot live probe) before relying on it; if the status field turns out not to be filter-exposed, fall back to app-side filtering using the returned status. This matches the ticket's own hedge ("expected behavior, not guaranteed across versions").

---

## 3. Service Request Ingestion

### 3.1 Authenticated REST creation — **exists** (full lifecycle)
Family: `/shop-management/{tenantId}/service-requests`

| Action | Method / path | DTO → response | Permission |
|---|---|---|---|
| **Create** | `POST /shop-management/{tenantId}/service-requests` | `CreateServiceRequestDto` → `ServiceRequest` | `serviceRequests:access` |
| Search | `POST /shop-management/{tenantId}/service-requests/search` | `FetchServiceRequestsDto` → `SearchServiceRequestsQueryResults` | (unspecified) |
| Read | `GET …/service-requests/{id}` | → `ServiceRequest` | `serviceRequests:access` |
| Update | `PUT …/service-requests/{id}` | `UpdateServiceRequestDto` → `ServiceRequest` | `serviceRequests:access` |
| Assign → WO | `PUT …/service-requests/{id}/assign-to-wo` | `AssignWorkOrderToServiceRequestDto` → `ServiceRequest` | `serviceRequests:createWO` |
| Close | `PUT …/service-requests/{id}/close` | `CloseServiceRequestDto` → `ServiceRequest` | `serviceRequests:close` |
| Schedule | `PUT …/service-requests/{id}/schedule` | `ScheduleServiceRequestDto` → `ServiceRequest` | `serviceRequests:schedule` |
| Get facility/tenant hash | `GET …/service-requests/{id}/facility-tenant-hash` | → `FacilityTenantHashDto` | `serviceRequests:access` |

This gives a clean ingestion → triage → work-order path entirely over authenticated REST. The "triage queue" is the service-request collection itself; `assign-to-wo` promotes a request into a work order.

### 3.2 [Inference item] Direct REST vs public kiosk endpoint
Both create a service request from the **same** body type (`CreateServiceRequestDto`), but differ fundamentally:

| | Authenticated REST | Public kiosk |
|---|---|---|
| Path | `POST /shop-management/{tenantId}/service-requests` | `POST /service-requests-public/{hash}/submit-service-request` |
| Auth | Bearer JWT + `serviceRequests:access` | Unauthenticated; gated by a per-facility `{hash}` in the URL |
| Tenant scoping | Explicit `{tenantId}` | Implied by the `{hash}` |
| Companion ops | Full lifecycle (search/read/update/assign/close/schedule) | `configuration`, `search-vehicles`, `search-vehicles-enhanced` only — submit-and-forget |
| How to obtain the gate | Standard API key | `{hash}` — note `GET …/service-requests/{id}/facility-tenant-hash` returns a `FacilityTenantHashDto`, i.e. hashes are RTA-issued per facility |

> **Caveat:** `-public` routes are named public but carry **no** formal OpenAPI security marking (no operation has a security requirement in the spec). Naming ≠ an authentication contract — treat the kiosk hash as a bearer-equivalent secret and confirm its behavior with RTA.

**For a server-to-server integration, use the authenticated REST create** — it is tenant-scoped, permissioned, auditable (API keys can carry a desktop username for attribution), and gives you the read/track lifecycle the kiosk path lacks.

### 3.3 Field mapping — Vehicle ID / Request Type / Comments / Requester / Attachments
> **GAP (do not fabricate):** The current `RTA_FLEET_API_MAP.md` snapshot does **not** enumerate the field-level contents of `CreateServiceRequestDto` (required vs optional). The DTO name is confirmed; its members are not in the pinned map. **Action:** resolve `CreateServiceRequestDto` (and `ServiceRequest`) from the live OpenAPI component schemas before finalizing the mapping. The table below aligns the ticket's external fields to the expected RTA concept and marks each RTA-side field name **TBC**.

| External request field | Expected RTA concept | RTA field (TBC against `CreateServiceRequestDto`) | Notes |
|---|---|---|---|
| Vehicle ID | Vehicle reference | `vehicleId` / `vehicleLinkId` **TBC** | Resolve first via §2.1 search → `items[].id`. Note per issue #7, some vehicle-nested reads use `vehicleLinkId`, not `vehicleId` — confirm which the SR DTO wants. |
| Request Type | SR category/type code | **TBC** | Likely a status/type code from a maintenance-system-codes list; enumerate valid codes. |
| Comments | Description / notes | **TBC** | Free text. |
| Requester | Submitter identity | **TBC** | Authenticated path may derive attribution from the API key's desktop username; kiosk path likely needs an explicit requester field. |
| Attachment payload | Separate upload, linked to entity | **not inline** | Attachments are separate endpoints, not part of the SR create body. Authenticated: `POST /shop-management/{tenantId}/attachments` (multipart-style `object` body). Public: `POST /attachments-public/{hash}/upload`. Create the SR first, then attach to its entity id. Confirm the SR entity is a supported attachment parent. |

---

## 4. Event Handling & Data Sync

### 4.1 Webhooks — **none documented**
No webhook section, top-level OpenAPI `webhooks` declaration, callback object, or webhook-named endpoint exists in the reviewed official sources. Supported conclusion: *no documented event mechanism* (not proof none exists privately). → **Poll** `POST …/service-requests/search` (filter by status/updated timestamp) for status changes.

### 4.2 Data Extract API (bulk cache)
Separate host, raw DB rows, etag cursor:
```
GET https://api.rtafleet.com/v0/extract/<tablename>?etag=<etag>&limit=<limit>
Authorization: Bearer <token>
```
- Perm `api:extractTable` — **grants full read of all tables**; RTA advises tightly restricting keys that hold it. Isolate on a dedicated least-privilege key.
- `limit` default 1,000, **max 1,000**. Response: `count`, `value[]`, and `nextEtag` when more remains; omission of `nextEtag` = end. Invalid table → 404.
- Table names come from a **data dictionary obtained by contacting RTA support** (not self-serve).
- **Semantics gaps:** deletes/tombstones, snapshot consistency during long extracts, etag retention/reset, and schema-change notifications are **not documented**. Store the last `nextEtag` transactionally and get RTA guidance before treating extracts as a durable CDC feed.

---

## 5. Architectural Recommendation

**Hybrid, REST-primary:**

1. **Asset lookup (read, interactive):** Direct REST `search-vehicles-enhanced`. Low latency, precise filters, tenant-scoped. Filter out-of-service at query level (§2.3, pending field confirmation).
2. **Service-request ingestion (write):** Direct **authenticated** REST `POST …/service-requests` — not the kiosk path — for scoping, permissions, attribution, and lifecycle tracking.
3. **Local vehicle-directory cache (bulk, offline):** Data Extract API on a scheduled job (nightly), etag-cursored, on an isolated `api:extractTable` key. Use only if you need a full local mirror; for on-demand lookups the REST search is sufficient and avoids the broad extract grant.
4. **Status tracking:** **Poll** `service-requests/search` (no webhooks). Choose an interval consistent with unknown rate limits; back off on 429.

**Do NOT** batch-extract for the write path or for real-time lookups — extract is read-only, capped at 1k rows/page, and semantically incomplete for change tracking. **Do NOT** design around webhooks or a documented token TTL — neither exists in the sources.

### Pre-build checklist (carried from issue #7)
- [ ] Re-pin & diff live OpenAPI; generate only the needed slice (vehicles + service-requests + attachments).
- [ ] Resolve `CreateServiceRequestDto` / `ServiceRequest` / `Vehicle` field schemas → finalize §3.3 mapping.
- [ ] Confirm the vehicle **status** field is filter-exposed (§2.3).
- [ ] Confirm required grant for any `Requires undefined permission` op you touch.
- [ ] Provision least-privilege keys (separate key for extract).
- [ ] Runtime-probe token TTL and 429 behavior; build re-auth-on-401 + backoff.

---

## Deliverable A — Authenticated sample requests (Postman/OpenAPI-ready)

Environment variables: `{{tenantId}}`, `{{clientId}}`, `{{clientSecret}}`, `{{token}}`.
Base (REST): `https://api.momentum-prd.rtafleet.com` · Base (extract): `https://api.rtafleet.com`

**1. Get token**
```
GET {{momentum}}/information-management/{{tenantId}}/integrations/get-api-token?clientId={{clientId}}&clientSecret={{clientSecret}}
→ 200 { "token": "<JWT>" }     # save to {{token}}
```

**2. Search vehicles (active only, facility-scoped) — perm vehicles:view**
```
POST {{momentum}}/asset-management/{{tenantId}}/vehicles/search-vehicles-enhanced
Authorization: Bearer {{token}}
Content-Type: application/json

{ "queryOptions": {
    "pagination": { "offset": 0, "limit": 50 },
    "filters": [ { "name": "<statusField-TBC>", "operator": "neq", "values": ["<OOS-code-TBC>"] } ],
    "sorts":   [ { "sortBy": "vehicleNumber", "sortOrder": "ASC" } ]
} }
```

**3. Create service request (triage queue) — perm serviceRequests:access**
```
POST {{momentum}}/shop-management/{{tenantId}}/service-requests
Authorization: Bearer {{token}}
Content-Type: application/json

{ /* CreateServiceRequestDto — resolve fields from live schema before use */
  "vehicleId": "<uuid from step 2>",
  "requestType": "<code-TBC>",
  "comments": "…"
}
```

**4. Poll open requests — perm serviceRequests:access**
```
POST {{momentum}}/shop-management/{{tenantId}}/service-requests/search
Authorization: Bearer {{token}}
{ "queryOptions": { "pagination": { "offset": 0, "limit": 50 }, "filters": [ /* status/updatedAt */ ] } }
```

**5. Bulk extract (cache) — perm api:extractTable, dedicated key**
```
GET {{extract}}/v0/extract/<tablename>?limit=1000
Authorization: Bearer {{token}}
# follow nextEtag: GET …/<tablename>?etag=<nextEtag>&limit=1000
```

> Requests 2–4 are runnable as written except for the **TBC** field names, which must be filled from the live component schemas. Request 1 is verified working via `scripts/rta-first-call.mjs`.
