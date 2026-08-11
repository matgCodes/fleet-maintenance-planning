#!/usr/bin/env python3
"""Prepare and merge tire-research batches produced through Codex tool calls.

This script never launches an external AI CLI and never modifies the inherited
``research_results.json`` file. It bootstraps a separate Codex result copy,
emits pending generic vehicle tasks, validates completed research batches, and
merges them atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_TASKS = Path("research_tasks.json")
DEFAULT_SEED_RESULTS = Path("research_results.json")
DEFAULT_CODEX_RESULTS = Path("codex_research_results.json")


class ValidationError(ValueError):
    """Raised when a task or research result violates the local contract."""


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}") from exc


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def task_index(tasks_path: Path) -> tuple[list[dict], dict[str, dict]]:
    tasks = load_json(tasks_path)
    if not isinstance(tasks, list):
        raise ValidationError(f"{tasks_path} must contain a JSON array")

    indexed: dict[str, dict] = {}
    for position, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ValidationError(f"Task {position} must be an object")
        task_id = task.get("taskId")
        vehicle = task.get("vehicle")
        if not isinstance(task_id, str) or not task_id:
            raise ValidationError(f"Task {position} has no valid taskId")
        if task_id in indexed:
            raise ValidationError(f"Duplicate taskId in {tasks_path}: {task_id}")
        if not isinstance(vehicle, dict):
            raise ValidationError(f"Task {task_id} has no vehicle object")
        for field in ("year", "make", "model"):
            if vehicle.get(field) in (None, ""):
                raise ValidationError(f"Task {task_id} has no vehicle.{field}")
        indexed[task_id] = task
    return tasks, indexed


def validate_url(value: object, task_id: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{task_id}: sourceUrl must be a non-empty string")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(f"{task_id}: sourceUrl is not an HTTP(S) URL: {value}")


def validate_result(result: object, known_tasks: dict[str, dict]) -> dict:
    if not isinstance(result, dict):
        raise ValidationError("Each research result must be an object")

    task_id = result.get("taskId")
    if task_id not in known_tasks:
        raise ValidationError(f"Unknown taskId in result batch: {task_id!r}")

    tire_data = result.get("tireData")
    metadata = result.get("researchMetadata")
    if not isinstance(tire_data, dict):
        raise ValidationError(f"{task_id}: tireData must be an object")
    if not isinstance(metadata, dict):
        raise ValidationError(f"{task_id}: researchMetadata must be an object")

    for field in ("frontTireSize", "rearTireSize"):
        value = tire_data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{task_id}: tireData.{field} must be non-empty")
    if not isinstance(tire_data.get("isStaggered"), bool):
        raise ValidationError(f"{task_id}: tireData.isStaggered must be boolean")

    for field in (
        "sourceName",
        "reliabilityRationale",
        "fleetEdgeCaseNotes",
    ):
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            raise ValidationError(f"{task_id}: researchMetadata.{field} must be non-empty")
    validate_url(metadata.get("sourceUrl"), task_id)

    score = metadata.get("reliabilityScore")
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
        raise ValidationError(
            f"{task_id}: researchMetadata.reliabilityScore must be an integer from 1 to 5"
        )

    return result


def validate_result_list(
    results: object, known_tasks: dict[str, dict], source_label: str
) -> list[dict]:
    if not isinstance(results, list):
        raise ValidationError(f"{source_label} must contain a JSON array")
    validated: list[dict] = []
    seen: set[str] = set()
    for result in results:
        valid = validate_result(result, known_tasks)
        task_id = valid["taskId"]
        if task_id in seen:
            raise ValidationError(f"Duplicate taskId in {source_label}: {task_id}")
        seen.add(task_id)
        validated.append(valid)
    return validated


def load_result_records(path: Path, known_tasks: dict[str, dict]) -> list[dict]:
    records = load_json(path)
    if not isinstance(records, list):
        raise ValidationError(f"{path} must contain a JSON array")
    seen: set[str] = set()
    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValidationError(f"Result {position} in {path} must be an object")
        task_id = record.get("taskId")
        if task_id not in known_tasks:
            raise ValidationError(f"Unknown taskId in {path}: {task_id!r}")
        if task_id in seen:
            raise ValidationError(f"Duplicate taskId in {path}: {task_id}")
        seen.add(task_id)
    return records


def classify_results(
    records: list[dict], known_tasks: dict[str, dict]
) -> tuple[list[dict], dict[str, str]]:
    valid: list[dict] = []
    invalid: dict[str, str] = {}
    for record in records:
        try:
            valid.append(validate_result(record, known_tasks))
        except ValidationError as exc:
            invalid[record["taskId"]] = str(exc)
    return valid, invalid


def initialize_results(seed_path: Path, codex_path: Path, known_tasks: dict[str, dict]) -> None:
    if codex_path.exists():
        existing = load_result_records(codex_path, known_tasks)
        valid, invalid = classify_results(existing, known_tasks)
        print(
            f"Codex result copy already exists: {codex_path} "
            f"({len(valid)} valid, {len(invalid)} invalid)"
        )
        return

    seed = load_result_records(seed_path, known_tasks)
    valid, invalid = classify_results(seed, known_tasks)
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_path, codex_path)
    print(
        f"Created Codex result copy: {codex_path} "
        f"({len(valid)} valid, {len(invalid)} invalid inherited results)"
    )


def load_codex_results(codex_path: Path, known_tasks: dict[str, dict]) -> list[dict]:
    if not codex_path.exists():
        raise ValidationError(
            f"Codex result copy not found: {codex_path}. Run the init command first."
        )
    return validate_result_list(load_json(codex_path), known_tasks, str(codex_path))


def pending_payload(tasks: list[dict], completed_ids: set[str], limit: int | None) -> list[dict]:
    pending = []
    for task in tasks:
        if task["taskId"] in completed_ids:
            continue
        pending.append(
            {
                "taskId": task["taskId"],
                "vehicle": task["vehicle"],
                "instructions": (
                    "Find the standard OEM factory front and rear tire sizes for the "
                    "base/fleet configuration. Use a directly supporting source URL, "
                    "state whether fitment is staggered, score reliability from 1 to 5, "
                    "and identify trim, axle, dual-rear-wheel, or specialty-equipment caveats."
                ),
            }
        )
        if limit is not None and len(pending) >= limit:
            break
    return pending


def merge_batch(
    batch_path: Path,
    codex_path: Path,
    known_tasks: dict[str, dict],
    replace_existing: bool,
) -> tuple[int, int]:
    current = load_result_records(codex_path, known_tasks)
    valid_current, invalid_current = classify_results(current, known_tasks)
    batch = validate_result_list(load_json(batch_path), known_tasks, str(batch_path))
    current_by_id = {item["taskId"]: item for item in current}
    valid_current_ids = {item["taskId"] for item in valid_current}

    collisions = sorted(item["taskId"] for item in batch if item["taskId"] in valid_current_ids)
    if collisions and not replace_existing:
        raise ValidationError(
            "Batch would replace existing Codex results; rerun with --replace-existing "
            f"only if intentional: {', '.join(collisions)}"
        )

    for item in batch:
        current_by_id[item["taskId"]] = item

    ordered = [current_by_id[task_id] for task_id in known_tasks if task_id in current_by_id]
    atomic_write_json(codex_path, ordered)
    return len(batch), len(ordered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--seed-results", type=Path, default=DEFAULT_SEED_RESULTS)
    parser.add_argument("--codex-results", type=Path, default=DEFAULT_CODEX_RESULTS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Copy inherited results into a separate Codex file")
    subparsers.add_parser("status", help="Validate and report Codex result progress")

    pending = subparsers.add_parser("pending", help="Emit pending generic vehicle tasks")
    pending.add_argument("--limit", type=int)
    pending.add_argument("--output", type=Path)

    merge = subparsers.add_parser("merge", help="Validate and atomically merge a result batch")
    merge.add_argument("batch", type=Path)
    merge.add_argument("--replace-existing", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        tasks, known_tasks = task_index(args.tasks)
        if args.command == "init":
            initialize_results(args.seed_results, args.codex_results, known_tasks)
            return 0

        records = load_result_records(args.codex_results, known_tasks)
        results, invalid = classify_results(records, known_tasks)
        completed_ids = {item["taskId"] for item in results}

        if args.command == "status":
            missing = [task["taskId"] for task in tasks if task["taskId"] not in completed_ids]
            print(f"Tasks: {len(tasks)}")
            print(f"Valid completed: {len(results)}")
            print(f"Invalid inherited: {len(invalid)}")
            print(f"Pending: {len(missing)}")
            for task_id, error in list(invalid.items())[:5]:
                print(f"Invalid {task_id}: {error}")
            if missing:
                print(f"Next pending: {missing[0]}")
                return 1
            return 0

        if args.command == "pending":
            if args.limit is not None and args.limit < 1:
                raise ValidationError("--limit must be at least 1")
            payload = pending_payload(tasks, completed_ids, args.limit)
            if args.output:
                atomic_write_json(args.output, payload)
                print(f"Wrote {len(payload)} pending task(s) to {args.output}")
            else:
                print(json.dumps(payload, indent=2))
            return 0

        if args.command == "merge":
            merged, total = merge_batch(
                args.batch,
                args.codex_results,
                known_tasks,
                args.replace_existing,
            )
            print(f"Merged {merged} result(s) into {args.codex_results}")
            print(f"Codex result total: {total}/{len(tasks)}")
            return 0

        raise AssertionError(f"Unhandled command: {args.command}")
    except ValidationError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
