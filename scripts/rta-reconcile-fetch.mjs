#!/usr/bin/env node
/**
 * rta-reconcile-fetch.mjs  (Issue #16)
 *
 * Authenticates with RTA Fleet using macOS Keychain credentials, retrieves every
 * vehicle page from search-vehicles-enhanced (sorted by vehicleNumber), and pipes
 * the sanitized records directly to build_reconciliation_manifest.py over stdin.
 *
 * Retains in memory only: id, vehicleNumber, year, make, model, serialNumber,
 * isArchive. serialNumber (VIN) is needed for the AC#3 VIN re-verification and is
 * NEVER written to stdout or disk — it flows only through the in-process pipe to
 * the Python builder, which reports aggregate counts only.
 *
 * Any extra CLI args are forwarded verbatim to the Python builder
 * (e.g. --dry-run, --output, --manifest).
 *
 * Safety constraints:
 *   - Never prints credentials, bearer token, token-request URL, VINs/serials,
 *     or raw response bodies. Progress/errors go to stderr as sanitized tokens.
 *   - Requires HTTP 200/201, stable pagination totals, unique RTA IDs, no
 *     repeated/empty pages, and retrieved count == totalRecords.
 *   - On any violation, exits non-zero with a sanitized error.
 */

import { execFileSync, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE_URL = "https://api.momentum-prd.rtafleet.com";
const PAGE_SIZE = 100;
const KEYCHAIN_SERVICES = Object.freeze({
  tenantId: "com.magstation.rta-fleet.tenant-id",
  clientId: "com.magstation.rta-fleet.client-id",
  clientSecret: "com.magstation.rta-fleet.client-secret",
});
const RETAINED_FIELDS = [
  "id",
  "vehicleNumber",
  "year",
  "make",
  "model",
  "serialNumber",
  "isArchive",
];

function readKeychainItem(service) {
  return execFileSync(
    "/usr/bin/security",
    ["find-generic-password", "-a", process.env.USER, "-s", service, "-w"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  ).trim();
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function sanitize(vehicle) {
  const out = {};
  for (const field of RETAINED_FIELDS) out[field] = vehicle[field] ?? null;
  return out;
}

function usage() {
  process.stderr.write(
    "Usage: ./scripts/rta-reconcile-fetch.mjs [builder-args...]\n\n" +
      "Fetches all RTA vehicles and pipes sanitized records to\n" +
      "build_reconciliation_manifest.py. VIN/serial values are never printed\n" +
      "or persisted. Extra args (e.g. --dry-run) are forwarded to the builder.\n",
  );
}

async function main() {
  const forwarded = process.argv.slice(2);
  if (forwarded.includes("--help") || forwarded.includes("-h")) {
    usage();
    return;
  }

  if (typeof fetch !== "function") {
    process.stderr.write("error=node_18_or_newer_required\n");
    process.exitCode = 1;
    return;
  }

  let tenantId, clientId, clientSecret;
  try {
    tenantId = readKeychainItem(KEYCHAIN_SERVICES.tenantId);
    clientId = readKeychainItem(KEYCHAIN_SERVICES.clientId);
    clientSecret = readKeychainItem(KEYCHAIN_SERVICES.clientSecret);
  } catch {
    process.stderr.write("keychain=read_failed\n");
    process.exitCode = 1;
    return;
  }
  if (!tenantId || !clientId || !clientSecret) {
    process.stderr.write("keychain=empty_value\n");
    process.exitCode = 1;
    return;
  }

  const tokenUrl = new URL(
    `${BASE_URL}/information-management/${encodeURIComponent(tenantId)}/integrations/get-api-token`,
  );
  tokenUrl.searchParams.set("clientId", clientId);
  tokenUrl.searchParams.set("clientSecret", clientSecret);

  let tokenResponse;
  try {
    tokenResponse = await fetch(tokenUrl, { method: "GET" });
  } catch {
    process.stderr.write("token_request=network_failed\n");
    process.exitCode = 1;
    return;
  }
  const tokenPayload = await readJson(tokenResponse);
  process.stderr.write(`token_http_status=${tokenResponse.status}\n`);
  const token =
    typeof tokenPayload?.token === "string"
      ? tokenPayload.token
      : typeof tokenPayload?.access_token === "string"
        ? tokenPayload.access_token
        : null;
  if (!tokenResponse.ok || !token) {
    process.stderr.write("token_received=no\n");
    process.exitCode = 1;
    return;
  }
  process.stderr.write("token_received=yes\n");

  const searchUrl = `${BASE_URL}/asset-management/${encodeURIComponent(tenantId)}/vehicles/search-vehicles-enhanced`;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const vehicles = [];
  const seenIds = new Set();
  let expectedTotal = null;
  let offset = 0;
  let page = 0;

  while (expectedTotal === null || offset < expectedTotal) {
    page += 1;
    const body = JSON.stringify({
      queryOptions: {
        pagination: { offset, limit: PAGE_SIZE },
        filters: [],
        sorts: [{ sortBy: "vehicleNumber", sortOrder: "ASC" }],
      },
    });
    let response;
    try {
      response = await fetch(searchUrl, { method: "POST", headers, body });
    } catch {
      process.stderr.write(`page=${page} network_failed\n`);
      process.exitCode = 1;
      return;
    }
    if (response.status !== 200 && response.status !== 201) {
      process.stderr.write(`page=${page} http_status=${response.status} expected=200_or_201\n`);
      process.exitCode = 1;
      return;
    }
    const payload = await readJson(response);
    if (!payload || !Array.isArray(payload.items) || !Number.isFinite(payload?.meta?.totalRecords)) {
      process.stderr.write(`page=${page} invalid_response_shape\n`);
      process.exitCode = 1;
      return;
    }
    if (expectedTotal === null) {
      expectedTotal = payload.meta.totalRecords;
      process.stderr.write(`total_records=${expectedTotal}\n`);
    } else if (payload.meta.totalRecords !== expectedTotal) {
      process.stderr.write(`page=${page} pagination_total_changed\n`);
      process.exitCode = 1;
      return;
    }
    for (const vehicle of payload.items) {
      if (vehicle.id == null || seenIds.has(vehicle.id)) {
        process.stderr.write(`page=${page} missing_or_duplicate_rta_id\n`);
        process.exitCode = 1;
        return;
      }
      seenIds.add(vehicle.id);
      vehicles.push(sanitize(vehicle));
    }
    process.stderr.write(`page=${page} offset=${offset} items_returned=${payload.items.length}\n`);
    offset += payload.items.length;
    if (payload.items.length === 0 && offset < expectedTotal) {
      process.stderr.write(`page=${page} premature_empty_page\n`);
      process.exitCode = 1;
      return;
    }
  }

  if (vehicles.length !== expectedTotal) {
    process.stderr.write(`integrity_check=FAILED retrieved=${vehicles.length} expected=${expectedTotal}\n`);
    process.exitCode = 1;
    return;
  }
  process.stderr.write(`fetch_complete total_retrieved=${vehicles.length} unique_ids=${seenIds.size}\n`);

  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const pythonScript = path.join(scriptDir, "build_reconciliation_manifest.py");
  const result = spawnSync("python3", [pythonScript, ...forwarded], {
    input: JSON.stringify(vehicles),
    encoding: "utf8",
    stdio: ["pipe", "pipe", "pipe"],
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) {
    process.stderr.write("python_builder=launch_failed\n");
    process.exitCode = 1;
    return;
  }
  process.exitCode = result.status ?? 1;
}

await main();
