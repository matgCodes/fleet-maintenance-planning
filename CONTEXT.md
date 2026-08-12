# RTA Fleet Integration

This context defines the canonical language used when discussing RTA Fleet API
access and core fleet-maintenance resources. It exists to prevent identity,
scope, and resource terms from being used interchangeably.

## Identity and access

**Tenant**:
An RTA customer environment addressed by a tenant ID in tenant-scoped API
paths.
_Avoid_: Account, client, facility

**Tenant ID**:
The identifier for a Tenant; RTA also calls it the Serial Number.
_Avoid_: Client ID, facility ID, resource ID

**Facility**:
An operational subdivision within a Tenant, identified separately by a
facility ID.
_Avoid_: Tenant, account

**API Key**:
The registered integration identity whose assigned permissions control API
access and whose credentials are the client ID and client secret.
_Avoid_: API token, bearer token

**Client ID**:
The non-token identifier for an API Key, paired with its client secret when
requesting an API token.
_Avoid_: Tenant ID, API token

**Client Secret**:
The confidential credential paired with a client ID when requesting an API
token.
_Avoid_: API token, tenant ID

**API Token**:
The JWT returned by RTA's token endpoint and sent as a Bearer token on later
requests.
_Avoid_: API key, client secret

**Permission**:
A resource-and-action grant assigned to an API Key, such as permission to view
vehicles or update parts.
_Avoid_: User role, API token

## API surfaces and access patterns

**Momentum REST API**:
The tenant-scoped operational API for RTA resources such as vehicles, parts,
work orders, fuel, users, and reports.
_Avoid_: Data Extract API

**Data Extract API**:
The separate API surface that returns raw database-table rows for warehousing
and utility use.
_Avoid_: Momentum REST API, reporting API

**Extract etag**:
A row-change cursor used by the Data Extract API to request rows changed after
the last successful extraction point.
_Avoid_: HTTP ETag, timestamp, page number

**Search endpoint**:
A collection query that returns matching items and pagination metadata, often
using a `POST` body containing `queryOptions`.
_Avoid_: Create endpoint, detail endpoint

**Resource ID**:
The stable identifier returned for an individual API resource and used by its
detail or mutation endpoints.
_Avoid_: Tenant ID, facility ID, display number

## Fleet-maintenance resources

**Vehicle**:
The fleet asset record around which meters, fuel, preventive maintenance,
inspections, warranties, and repair activity are organized.
_Avoid_: Vehicle number, work order

**Vehicle number**:
The business-facing number used to find a Vehicle; it is not the Vehicle's
resource ID.
_Avoid_: Vehicle ID, serial number

**Work Order**:
A maintenance or repair record associated with a Vehicle and containing one or
more work-order lines. It is the authoritative record of corrective work.
_Avoid_: Work-order line, purchase order

**Work-order line**:
A child unit of maintenance or repair work within a Work Order.
_Avoid_: Work order, part posting

**Part**:
An inventory item that can be stocked, purchased, requested, or posted to
maintenance work.
_Avoid_: Part posting, purchase-order line

**Purchase Order**:
A procurement record connecting a vendor and facility to ordered lines and
receipts.
_Avoid_: Work order, purchase-order line

## Asset identity and tire fitment

**Fleet asset**:
A physical vehicle, trailer, or equipment unit tracked by the fleet. A Fleet
asset may lack a current or unique matching Vehicle record in RTA.
_Avoid_: Vehicle, vehicle record

**Asset number**:
The fleet's business-facing identifier for a Fleet asset and the primary key
for cross-referencing fleet inventory records.
_Avoid_: Vehicle resource ID, VIN, serial number

**Asset identity**:
The identifying facts for a Fleet asset: Asset number, year, make, model, and
VIN where one exists. Tire research does not override Asset identity.
_Avoid_: Tire-research description, asset-number match alone

**VIN**:
The manufacturer-issued vehicle identification number, represented by RTA in
the `serialNumber` field. Some Fleet assets have no standard VIN.
_Avoid_: Vehicle number, Vehicle resource ID, tenant serial number

**Researched tire fitment**:
An evidence-backed front and rear tire-size result associated with a stated
year, make, and model. It is not proof of the tires installed on a specific
Fleet asset.
_Avoid_: Asset identity, unit-confirmed tire fitment

**Unit-confirmed tire fitment**:
The front and rear tire sizes verified for the specific Fleet asset from the
unit, its placard, or unit-specific documentation.
_Avoid_: Researched tire fitment, generic model fitment

**Approved fitment with warning**:
A Researched tire fitment accepted for operational use even though the Fleet
asset's identity evidence is incomplete or differs from the research identity.
_Avoid_: Unit-confirmed fitment, unresolved fitment

**Unresolved fitment**:
A Fleet asset for which available identity and research evidence do not support
a tire-size assignment. Its tire-size fields remain blank pending confirmation.
_Avoid_: Approved fitment with warning, missing Fleet asset

## Inspection records

**Driver Inspection**:
A completed operator checklist in Fleet360, called Paperless Driver Inspection
in some RTA documentation. It is the authoritative weekly checklist record.
_Avoid_: Driver Report, RTA Inspect, Mechanic Vehicle Inspection

**Driver Report**:
The Fleet360 record used by shop staff to review and route a defect reported
through a Driver Inspection. It is not the completed inspection checklist.
_Avoid_: Driver Inspection, Work Order

**Mechanic Vehicle Inspection**:
A template-based shop inspection completed by an authorized technician and
associated with a work-order line. It is the authoritative mechanic and DOT
inspection record.
_Avoid_: Driver Inspection, Work Order, Tire Inspection, Brake Inspection

**Tire Inspection**:
The authoritative record of tire-condition measurements by axle and wheel
position.
_Avoid_: Mechanic Vehicle Inspection, Brake Inspection

**Brake Inspection**:
The authoritative record of brake-condition measurements for a Vehicle.
_Avoid_: Mechanic Vehicle Inspection, Tire Inspection

**Inspection template**:
A reusable, versioned definition of the sections, items, prompts, and defects
used to perform an inspection. It is assigned by vehicle class or equipment
configuration and is not a completed inspection.
_Avoid_: Inspection record, work-order template

**Inspection verification**:
A separate post-repair inspection that confirms whether a failed condition was
corrected. It is associated with the original finding through the corrective
Work Order and does not replace the original inspection.
_Avoid_: Inspection edit, work-order closure

**Critical inspection finding**:
An inspection result that makes a Vehicle unavailable until corrective work and
Inspection verification are complete.
_Avoid_: Warning condition, deferred maintenance

**RTA Inspect**:
A separately licensed mobile inspection product that can retain completed
inspections and send failed items into Fleet360.
_Avoid_: Driver Inspection, Driver Report, RTA Mobile Paperless Shop
