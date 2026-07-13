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
more work-order lines.
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
