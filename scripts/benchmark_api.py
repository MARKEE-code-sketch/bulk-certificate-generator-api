"""Run a small local HTTP benchmark against the certificate API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import httpx


TERMINAL_STATES = {"completed", "completed_with_errors"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_until_ready(client: httpx.AsyncClient, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Uvicorn exited before becoming ready.")
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.2)
    raise RuntimeError("Timed out waiting for the local API to start.")


async def run_workload(
    base_url: str,
    request_count: int,
    workers: int,
    process: subprocess.Popen,
) -> dict[str, object]:
    statuses: Counter[int] = Counter()
    errors: list[str] = []
    total_requests = 0
    semaphore = asyncio.Semaphore(workers)
    payload = {
        "event_name": "Local API benchmark",
        "issue_date": "2026-10-08",
        "issuer_name": "Benchmark",
        "recipients": [{"name": "Test Person", "email": "test@example.com"}],
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        await wait_until_ready(client, process)  # Readiness is outside measured totals.
        start = time.perf_counter()

        async def submit_one(request_number: int) -> str | None:
            nonlocal total_requests
            async with semaphore:
                try:
                    response = await client.post("/api/v1/certificate-jobs", json=payload)
                    total_requests += 1
                    statuses[response.status_code] += 1
                    if response.status_code != 202:
                        errors.append(f"POST {request_number}: HTTP {response.status_code}")
                        return None
                    job_id = response.json().get("job_id")
                    if not isinstance(job_id, str):
                        errors.append(f"POST {request_number}: response had no job_id")
                        return None
                    return job_id
                except (httpx.HTTPError, ValueError) as exc:
                    total_requests += 1
                    errors.append(f"POST {request_number}: {type(exc).__name__}: {exc}")
                    return None

        submission_start = time.perf_counter()
        job_ids = await asyncio.gather(*(submit_one(i + 1) for i in range(request_count)))
        submission_elapsed = time.perf_counter() - submission_start
        job_ids = [job_id for job_id in job_ids if job_id]

        async def wait_for_job(job_id: str) -> None:
            nonlocal total_requests
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    async with semaphore:
                        response = await client.get(f"/api/v1/certificate-jobs/{job_id}")
                    total_requests += 1
                    statuses[response.status_code] += 1
                    if response.status_code != 200:
                        errors.append(f"GET job {job_id}: HTTP {response.status_code}")
                        return
                    state = response.json().get("status")
                    if state in TERMINAL_STATES:
                        return
                except (httpx.HTTPError, ValueError) as exc:
                    total_requests += 1
                    errors.append(f"GET job {job_id}: {type(exc).__name__}: {exc}")
                    return
                await asyncio.sleep(0.1)
            errors.append(f"GET job {job_id}: timed out waiting for completion")

        await asyncio.gather(*(wait_for_job(job_id) for job_id in job_ids))
        elapsed = time.perf_counter() - start

    return {
        "requested_jobs": request_count,
        "accepted_jobs": len(job_ids),
        "submission_elapsed_seconds": submission_elapsed,
        "accepted_jobs_per_second": (
            len(job_ids) / submission_elapsed if submission_elapsed else 0.0
        ),
        "total_requests": total_requests,
        "status_code_counts": dict(sorted(statuses.items())),
        "elapsed_seconds": elapsed,
        "requests_per_second": total_requests / elapsed if elapsed else 0.0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=10, help="number of one-recipient jobs to submit")
    parser.add_argument("--workers", type=int, default=2, help="maximum concurrent HTTP operations")
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1:
        parser.error("--requests and --workers must both be at least 1")

    project_dir = Path(__file__).resolve().parents[1]
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="certificate-api-benchmark-") as temp_dir:
        temp_path = Path(temp_dir)
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{(temp_path / 'benchmark.db')}"
        env["CERTIFICATE_OUTPUT_DIR"] = str(temp_path / "certificates")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=project_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            results = asyncio.run(
                run_workload(
                    f"http://127.0.0.1:{port}", args.requests, args.workers, process
                )
            )
            print(json.dumps(results, indent=2))
            return 1 if results["errors"] else 0
        except Exception as exc:
            print(f"Benchmark failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
