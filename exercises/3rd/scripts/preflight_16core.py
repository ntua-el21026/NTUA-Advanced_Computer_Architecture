#!/usr/bin/env python3
"""Validate the host and Docker setup before running Assignment 3."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from run_4_1_real_scalability import discover_physical_cpus


BASE_IMAGE = (
    "snipersim/snipersim@"
    "sha256:4f10d4bbfee057e27a52fc0dc33087813feb504bbbfff22902984e356576eaed"
)


def command_version(command: list[str]) -> str:
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False
    )
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0] if output else f"exit {completed.returncode}"


def docker_shell_check(image: str) -> tuple[bool, str]:
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/bin/bash",
            image,
            "-lc",
            "true",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True, "PASS"
    if completed.returncode == 139:
        return False, (
            "CentOS 6 shell exited with SIGSEGV (139). Configure WSL with "
            "vsyscall=emulate; see exercises/3rd/scripts/README.md."
        )
    details = (completed.stderr or completed.stdout).strip()
    return False, f"exit {completed.returncode}: {details}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-physical", type=int, default=16)
    parser.add_argument("--expected-logical", type=int, default=24)
    parser.add_argument("--image", default=BASE_IMAGE)
    parser.add_argument("--skip-docker", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    failures: list[str] = []

    required = ["gcc", "make", "python3", "lscpu", "git", "git-lfs"]
    if not args.skip_docker:
        required.append("docker")
    for command in required:
        path = shutil.which(command)
        print(f"{command:<10} {path or 'MISSING'}")
        if path is None:
            failures.append(f"missing command: {command}")

    physical = discover_physical_cpus()
    logical = len(os.sched_getaffinity(0))
    representatives = [cpu.representative for cpu in physical]
    print(f"logical CPUs available:  {logical}")
    print(f"physical cores available: {len(physical)}")
    print("physical representatives: " + ",".join(map(str, representatives)))

    if len(physical) != args.expected_physical:
        failures.append(
            f"expected {args.expected_physical} physical cores, "
            f"found {len(physical)}"
        )
    if logical != args.expected_logical:
        failures.append(
            f"expected {args.expected_logical} logical CPUs, found {logical}"
        )

    if shutil.which("git-lfs"):
        print("Git LFS:", command_version(["git", "lfs", "version"]))
        lfs = subprocess.run(
            ["git", "lfs", "fsck"], capture_output=True, text=True, check=False
        )
        if lfs.returncode != 0:
            failures.append("git lfs fsck failed")
        else:
            print("Git LFS objects: PASS")

    if not args.skip_docker and shutil.which("docker"):
        docker_version = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if docker_version.returncode != 0:
            failures.append("Docker daemon is unavailable")
        else:
            print("Docker daemon: PASS")
            inspect = subprocess.run(
                ["docker", "image", "inspect", args.image],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if inspect.returncode != 0:
                print(f"Pulling {args.image}")
                pull = subprocess.run(["docker", "pull", args.image], check=False)
                if pull.returncode != 0:
                    failures.append("failed to pull Sniper image")
            if not failures or inspect.returncode == 0:
                ok, detail = docker_shell_check(args.image)
                print(f"CentOS 6 compatibility: {detail}")
                if not ok:
                    failures.append(detail)

    root = Path(__file__).resolve().parents[3]
    free_gib = shutil.disk_usage(root).free / 1024**3
    print(f"free workspace disk: {free_gib:.1f} GiB")
    if free_gib < 30:
        failures.append("less than 30 GiB free disk space")

    if failures:
        print("\nPreflight: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nPreflight: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
