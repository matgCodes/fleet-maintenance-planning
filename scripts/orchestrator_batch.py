import subprocess
import json
import os
import time

TASKS_FILE = "research_tasks.json"
RESULTS_FILE = "research_results.json"

def run_batch():
    if not os.path.exists(TASKS_FILE):
        print(f"❌ Could not find {TASKS_FILE}")
        return

    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    # Load existing results to allow resuming if interrupted
    results = []
    completed_task_ids = set()
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                results = json.load(f)
                completed_task_ids = {r.get("taskId") for r in results}
        except json.JSONDecodeError:
            pass

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

    schema_json = json.dumps(response_schema)
    total_tasks = len(tasks)

    for i, task in enumerate(tasks):
        task_id = task.get("taskId")
        vehicle = task.get("vehicle", {})

        if task_id in completed_task_ids:
            print(f"[{i+1}/{total_tasks}] ⏩ Skipping {task_id} (already completed)")
            continue

        print(f"[{i+1}/{total_tasks}] 🔍 Researching {task_id}: {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}...")

        prompt = f"""
        You are an expert automotive fleet researcher.
        Find the standard OEM factory tire size for the base/fleet trim of this vehicle:
        Year: {vehicle.get('year')}
        Make: {vehicle.get('make')}
        Model: {vehicle.get('model')}

        Task ID: {task_id}

        Instructions:
        1. Determine if the vehicle has staggered tires (different sizes front and rear) or square (same size).
        2. Provide a reliability score from 1 to 5 based on your confidence and source quality.
        3. Include the source name and URL you referenced (e.g., wheel-size.com, ford.com, etc.).
        4. Note any edge cases (like Police Interceptor or heavy-duty trims using different sizes).
        """

        cmd = [
            "agy", "--print", prompt,
            "--json-schema", schema_json,
            "--output-format", "json",
            "--model", "Claude Sonnet 4.6 (Thinking)"
        ]

        # Retry logic: up to 3 attempts with exponential backoff
        attempts = 0
        while attempts < 3:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                raw_output = result.stdout.strip()
                envelope = json.loads(raw_output)
                parsed_data = envelope.get("structured_output")
                if not parsed_data:
                    print(f"⚠️ Warning: No structured_output returned for {task_id}")
                    break
                # Append and save continuously
                results.append(parsed_data)
                with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                print(f"  ✅ Success: {parsed_data.get('tireData', {}).get('frontTireSize')} (Score: {parsed_data.get('researchMetadata', {}).get('reliabilityScore')})")
                break  # success, exit retry loop
            except subprocess.CalledProcessError as e:
                attempts += 1
                wait = 2 ** attempts
                print(f"  ❌ Shell Error on {task_id} (attempt {attempts}/3): {e.stderr.strip()}")
                print(f"     Retrying in {wait}s...")
                time.sleep(wait)
            except json.JSONDecodeError as e:
                attempts += 1
                wait = 2 ** attempts
                print(f"  ❌ JSON Error on {task_id} (attempt {attempts}/3): {e}")
                print(f"     Retrying in {wait}s...")
                time.sleep(wait)
        else:
            print(f"  ❌ Failed after 3 attempts for {task_id}. Skipping.")

        # Short pause between tasks to avoid hitting rate limits
        time.sleep(2)

    print(f"\n🎉 Batch Execution Complete! Generated {len(results)} results in {RESULTS_FILE}")

if __name__ == "__main__":
    run_batch()
