#!/usr/bin/env node

import { execFileSync } from "node:child_process";

const BASE_URL = "https://api.momentum-prd.rtafleet.com";

const KEYCHAIN_SERVICES = Object.freeze({
  tenantId: "com.magstation.rta-fleet.tenant-id",
  clientId: "com.magstation.rta-fleet.client-id",
  clientSecret: "com.magstation.rta-fleet.client-secret",
});

function printUsage() {
  console.log(`Usage: ./scripts/rta-first-call.mjs

Authenticates with RTA Fleet using credentials stored in macOS Keychain, then
runs a read-only vehicle search limited to one record. The script prints only
HTTP status codes, response keys, and record counts.

It never prints the credentials, token, token-request URL, or vehicle details.`);
}

function readKeychainItem(service) {
  return execFileSync(
    "/usr/bin/security",
    [
      "find-generic-password",
      "-a",
      process.env.USER,
      "-s",
      service,
      "-w",
    ],
    {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    },
  ).trim();
}

function responseKeys(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return typeof value;
  }

  return Object.keys(value).sort().join(",");
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function main() {
  if (process.argv.includes("--help") || process.argv.includes("-h")) {
    printUsage();
    return;
  }

  if (process.argv.length > 2) {
    console.error("error=unknown_argument");
    printUsage();
    process.exitCode = 2;
    return;
  }

  if (typeof fetch !== "function") {
    console.error("error=node_18_or_newer_required");
    process.exitCode = 1;
    return;
  }

  let tenantId;
  let clientId;
  let clientSecret;

  try {
    tenantId = readKeychainItem(KEYCHAIN_SERVICES.tenantId);
    clientId = readKeychainItem(KEYCHAIN_SERVICES.clientId);
    clientSecret = readKeychainItem(KEYCHAIN_SERVICES.clientSecret);
  } catch {
    console.error("keychain=read_failed");
    console.error(
      "Check that the tenant ID, client ID, and client secret Keychain items exist.",
    );
    process.exitCode = 1;
    return;
  }

  if (!tenantId || !clientId || !clientSecret) {
    console.error("keychain=empty_value");
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
    console.error("token_request=network_failed");
    process.exitCode = 1;
    return;
  }

  const tokenPayload = await readJson(tokenResponse);
  console.log(`token_http_status=${tokenResponse.status}`);
  console.log(`token_response_keys=${responseKeys(tokenPayload)}`);

  const token =
    typeof tokenPayload?.token === "string"
      ? tokenPayload.token
      : typeof tokenPayload?.access_token === "string"
        ? tokenPayload.access_token
        : null;

  if (!tokenResponse.ok || !token) {
    console.error("token_received=no");
    process.exitCode = 1;
    return;
  }

  console.log("token_received=yes");

  let vehicleResponse;
  try {
    vehicleResponse = await fetch(
      `${BASE_URL}/asset-management/${encodeURIComponent(tenantId)}/vehicles/search-vehicles-enhanced`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          queryOptions: {
            pagination: { offset: 0, limit: 1 },
            filters: [],
            sorts: [],
          },
        }),
      },
    );
  } catch {
    console.error("vehicle_search=network_failed");
    process.exitCode = 1;
    return;
  }

  const vehiclePayload = await readJson(vehicleResponse);
  console.log(`vehicle_search_http_status=${vehicleResponse.status}`);
  console.log(
    `vehicle_search_response_keys=${responseKeys(vehiclePayload)}`,
  );
  console.log(
    `vehicle_search_items_returned=${Array.isArray(vehiclePayload?.items) ? vehiclePayload.items.length : "unknown"}`,
  );
  console.log(
    `vehicle_search_total_records=${Number.isFinite(vehiclePayload?.meta?.totalRecords) ? vehiclePayload.meta.totalRecords : "unknown"}`,
  );

  if (!vehicleResponse.ok) {
    process.exitCode = 1;
  }
}

await main();
