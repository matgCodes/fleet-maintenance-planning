import subprocess
import json
import os

def run_prototype():
    vehicle = {
        "year": "2024",
        "make": "DODGE",
        "model": "DURANGO"
    }

    # Defining the strict JSON schema expected
    response_schema = {
        "type": "object",
        "properties": {
            "taskId": {"type": "string"},
            "tireData": {
                "type": "object",
                "properties": {
                    "frontTireSize": {"type": "string"},
                    "rearTireSize": {"type": "string"},
                    "isStaggered": {"type": "boolean"}
                },
                "required": ["frontTireSize", "rearTireSize", "isStaggered"]
            },
            "researchMetadata": {
                "type": "object",
                "properties": {
                    "sourceName": {"type": "string"},
                    "sourceUrl": {"type": "string"},
                    "reliabilityScore": {"type": "integer", "description": "1 to 5"},
                    "reliabilityRationale": {"type": "string"},
                    "fleetEdgeCaseNotes": {"type": "string"}
                },
                "required": ["sourceName", "sourceUrl", "reliabilityScore", "reliabilityRationale", "fleetEdgeCaseNotes"]
            }
        },
        "required": ["taskId", "tireData", "researchMetadata"]
    }

    prompt = f"""
    You are an expert automotive fleet researcher.
    Find the standard OEM factory tire size for the base/fleet trim of this vehicle:
    Year: {vehicle['year']}
    Make: {vehicle['make']}
    Model: {vehicle['model']}

    Task ID: veh_001

    Instructions:
    1. Determine if the vehicle has staggered tires (different sizes front and rear) or square (same size).
    2. Provide a reliability score from 1 to 5 based on your confidence and source quality.
    3. Include the source name and URL you referenced (e.g., wheel-size.com, ford.com, etc.).
    4. Note any edge cases (like Police Interceptor or heavy-duty trims using different sizes).
    """

    print(f"Sending request to agy (Gemini 3.1 Pro (High)) for {vehicle['year']} {vehicle['make']} {vehicle['model']}...")

    cmd = [
        "agy", "--print", prompt,
        "--json-schema", json.dumps(response_schema),
        "--output-format", "json",
        "--model", "Gemini 3.1 Pro (High)"
    ]

    try:
        # We use subprocess to shell out to the local Antigravity environment (agy CLI)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_output = result.stdout.strip()

        # Strip potential markdown blocks if present
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:-3].strip()
        elif raw_output.startswith("```"):
            raw_output = raw_output[3:-3].strip()

        print("\n--- Raw JSON Response ---")
        print(raw_output)

        print("\n--- Parsed Object ---")
        data = json.loads(raw_output)
        print(json.dumps(data, indent=2))

        print("\n✅ AI Prompt and Schema Prototype Successful via Antigravity Quota!")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during AI generation: {e.stderr}")
    except json.JSONDecodeError as e:
        print(f"\n❌ Failed to parse JSON: {e}")
        print("Raw output was:", raw_output)

if __name__ == "__main__":
    run_prototype()
