# Canonical Municipal Vehicle Record — Field Inventory

**Issue:** [#2 Define the canonical municipal vehicle record](https://github.com/matgCodes/fleet-maintenance-planning/issues/2)
**Verified:** 2026-07-13 against live OpenAPI (`/api-json`) + one read-only sampled record (`search-vehicles-enhanced`). Schema metadata and record *shape* only — no field values or PII inspected.

"Municipal vehicle record" is this tenant's instance of the RTA `Vehicle` resource. The classification below is what the sources support; the per-category axis is not yet defined (see §7).

## 1. Authoritative identity + required core

The `Vehicle` schema marks exactly **five** fields required:

| Field | Role |
|---|---|
| `id` | Resource ID (UUID), system-assigned — the record's true key |
| `vehicleNumber` | Business-facing number (not the ID) |
| `vehicleLinkNumber` | Numeric link key |
| `facilityId` | Owning facility scope |
| `fuelType` | — |

`tenantId`, `etag`, `rowId` appear on the live record but are **not** in the published schema — treat as system/infra fields.

## 2. Required-on-create is a documented conflict

`CreateVehicleDto.required = []` — the create contract requires nothing, yet the read model requires the five above. Requiredness is enforced by server behavior/derivation (e.g. facility from `selectedFacilityId`), not the spec. Do not trust the spec's create-requiredness; confirm against runtime.

## 3. Conditional (present only when a relationship/feature is in use)

- **Classification/ownership:** `classId`/`class`, `departmentId`/`department`, `customerId`/`customer`, `regions`, `operator`/`operatorEmployee`, `parentAssets`/`childAssets`
- **Lifecycle-gated:** `isLeased`→`vehicleLease`; `isArchive`→`lastArchiveDate`; sale (`saleDate`, `salePrice`); `registrationExpirationDate`
- **Subresources returned on detail, not search:** `alternateMeters`, `campaignLines`, `crossReferenceNumbers`, `warrantyClaims`, `workOrders`, `reservation`, `efiTransactions`, `assetInfo`, `popupNotes`

## 4. Derived / computed (system-maintained, not authored)

- **Financial rollups:** `depreciationAccumulated|PerPeriod|ThisYear`, `appreciation*`, `errFund*`, `insuranceAccumulated|PerPeriod|PerYear|ThisYear`, `licensingAccumulated|PerPeriod|PerYear|ThisYear`, `monthsAppreciated`
- **Telemetry rollups:** `averageMPG`/`validAverageMPG`, `meters.workMeter`, `condition`/`conditionLastUpdatedDate`

## 5. Explicitly unused unless the tenant configures them

- `value01`–`value22` — 22 user-definable fields (empty on the sample)
- `customFields` / `vehicleCustomFieldValues`

## 6. Schema-vs-live divergences to record

- `operator`: schema `object`, live `string`
- `validAverageMPG`: schema `object`, live `number`
- Live-only (not in schema): `etag`, `rowId`, `tenantId`, `isNotesConverted`, `isOutsideVehicle`, `rearEndCapacity`
- **No `vin` property in the read schema** — VIN is managed only via `PUT /vehicles/{vehicleId}/vin` + `check-vehicle-vin-plate-allowed`; `serialNumber` is the nearest stored field. Treat VIN as a managed attribute, not a base record field.
- The search endpoint returns **HTTP 201** for a read-only query.

## 7. Open decision: "in-scope vehicle category"

The record has **no single "category" field**. Candidate axes, all present: `class`/`classId` (`VehicleClass`), `department`, `weightClass`/`numericalGrossVehicleWeight`, `regions`. Which one defines "in-scope vehicle category," the enumerated list, and which optional fields each category mandates are project decisions not yet recorded. Once named, the per-category required/conditional/derived/unused matrix can be built on top of this inventory.
