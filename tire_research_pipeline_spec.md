
## Problem Statement

The fleet technicians currently face hundreds of hours of manual physical inspection and data entry to determine the front and rear tire sizes for every vehicle in the fleet (429 assets). Typing this data from scratch on a tablet or clipboard is error-prone, tedious, and highly inefficient.

## Solution

We will build a two-part automated pipeline (an Orchestrator and an AI Research Agent) that pre-populates a "rough draft" of the OEM factory tire sizes into the `Asset_Tire_Inventory.xlsx` spreadsheet based on the vehicle's Year, Make, and Model. The technician's job shifts from "typing everything from scratch" to simply "verifying the pre-filled sizes and only editing them if the vehicle has been modified."

To save API calls and compute, the Orchestrator will deduplicate the 429 assets down to 175 unique configurations. The AI Research Agent will process these unique configurations using a strict JSON contract, returning the sizes, the source, and a 1-5 reliability score. The Orchestrator will fan these results back out to the Excel sheet, applying light background colors to indicate the trust level of the AI's research.

## User Stories

1. As a fleet data manager, I want the system to group identical vehicles (e.g., all 2024 Dodge Durangos) into a single research task, so that we don't waste time and API credits researching the same vehicle multiple times.
2. As a fleet data manager, I want the Orchestrator to assign generic task IDs (e.g., `veh_001`) instead of specific asset numbers, so that the AI Research Agent is completely decoupled from our internal asset tracking.
3. As an AI Research Agent, I want to receive a strict JSON payload containing the Year, Make, and Model, so that I know exactly what to look up in the wheel/tire databases.
4. As an AI Research Agent, I want to return a JSON payload with `frontTireSize` and `rearTireSize`, so that staggered fitments (like dual rear wheels) are handled correctly.
5. As an AI Research Agent, I want to provide a `reliabilityScore` (1-5) and a `sourceUrl`, so that the humans can audit the trustworthiness of my findings.
6. As a fleet technician in the field, I want the spreadsheet's Front and Rear Tire Size columns to be pre-filled with the OEM sizes, so that I only have to look at the tire to confirm it, rather than typing it.
7. As a fleet technician in the field, I want the cells to be color-coded (e.g., green for high confidence, yellow for low confidence), so that I know how much scrutiny to apply during my physical inspection.
8. As a fleet data manager, I want the Orchestrator to output the source URLs and AI reasoning to an internal text/JSON log rather than placing them in Excel Comments, so that the spreadsheet remains clean and lightweight for the field technicians.

## Implementation Decisions

- **Architecture:** Two decoupled systems. The Orchestrator (Node.js or Python) and the AI Research Agent.
- **Data Contract (Orchestrator -> Agent):**
  ```json
  {
    "taskId": "veh_001",
    "vehicle": {
      "year": "2025",
      "make": "FORD",
      "model": "EXPLORER"
    },
    "instructions": "Find the standard OEM factory tire size..."
  }
  ```
- **Data Contract (Agent -> Orchestrator):**
  ```json
  {
    "taskId": "veh_001",
    "tireData": {
      "frontTireSize": "255/65R18",
      "rearTireSize": "255/65R18",
      "isStaggered": false
    },
    "researchMetadata": {
      "sourceName": "Wheel-Size.com",
      "sourceUrl": "https://www....",
      "reliabilityScore": 4,
      "reliabilityRationale": "Matched exact year/make/model...",
      "fleetEdgeCaseNotes": "Police trims differ..."
    }
  }
  ```
- **Excel Injection:** Use Python (`openpyxl`) to inject sizes into Columns E and F. Use `openpyxl.styles.PatternFill` to color the cells based on the `reliabilityScore`.
- **Logging:** Write the `researchMetadata` to an internal `research_audit.json` log file rather than cluttering the Excel workbook.

## Testing Decisions

To ensure maximum reliability, we will test the pipeline at the JSON contract boundary. This is the highest and most robust seam.

- **Seam 1 (Orchestrator Injection Test):** We will provide a mock JSON array containing fake Agent results (e.g., one `veh_001` with score 5, one `veh_002` with score 2). We will run the Orchestrator injection script on a dummy Excel file and assert that the correct sizes were written to the correct rows, and that the cell background colors match the scores.
- **Seam 2 (Research Agent Prompt Test):** We will feed a mock `veh_001` payload to the Research Agent and validate that the output strictly conforms to the JSON schema (no missing keys, integers where expected, booleans where expected).

## Out of Scope

- Integrating directly with the RTA API for tire sizes (since OEM lookups require external web research).
- Automatically verifying if a vehicle has been modified with aftermarket parts (only humans can do this via physical inspection).
- Adding complex Excel macros, formulas, or cell comments to the final workbook.

## Further Notes

- The initial Python extraction script revealed 429 enriched assets map down to just 175 unique configurations, proving the high leverage of the Orchestrator design.
