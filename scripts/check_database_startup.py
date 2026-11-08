"""Reproduce a late database-network attachment using disposable local containers."""

import argparse
import json
import subprocess
import time
import uuid


def docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, timeout=120
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expect-dns-failure", action="store_true")
    options = parser.parse_args()
    prefix = "washday-startup-" + uuid.uuid4().hex[:8]
    app_network, db_network = prefix + "-appnet", prefix + "-dbnet"
    app, database = prefix + "-web", prefix + "-db"
    try:
        docker("network", "create", app_network)
        docker("network", "create", db_network)
        docker(
            "run", "-d", "--name", database, "--network", db_network,
            "--network-alias", "startup-db", "--tmpfs", "/var/lib/postgresql/data",
            "-e", "POSTGRES_DB=washday", "-e", "POSTGRES_USER=washday",
            "-e", "POSTGRES_PASSWORD=fixture-only", "postgres:17-alpine",
        )
        for _ in range(40):
            if docker("exec", database, "pg_isready", "-U", "washday", check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("Fixture PostgreSQL did not start")
        docker(
            "run", "-d", "--name", app, "--network", app_network,
            "-e", "DJANGO_SECRET_KEY=fixture-only-key",
            "-e", "DJANGO_ALLOWED_HOSTS=localhost",
            "-e", "PGDATABASE=washday", "-e", "PGHOST=startup-db",
            "-e", "PGUSER=washday", "-e", "PGPASSWORD=fixture-only", options.image,
        )
        # Match Openship's compose ordering: start first, attach the DB network later.
        time.sleep(12)
        state = json.loads(docker("inspect", app).stdout)[0]
        if options.expect_dns_failure:
            logs = docker("logs", app)
            assert not state["State"]["Running"]
            assert state["State"]["ExitCode"] != 0
            assert "failed to resolve host" in logs.stdout + logs.stderr
            print("REPRODUCED: startup exited before the database network was attached.", flush=True)
        else:
            assert state["State"]["Running"], docker("logs", app).stderr
            assert state["RestartCount"] == 0
        docker("network", "connect", db_network, app)
        if options.expect_dns_failure:
            docker("start", app)
        probe = (
            "import urllib.request; r=urllib.request.Request("
            "'http://127.0.0.1:8000/health/',headers={'X-Forwarded-Proto':'https'}); "
            "assert urllib.request.urlopen(r,timeout=3).status==200"
        )
        for _ in range(60):
            if docker("exec", app, "python", "-c", probe, check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            logs = docker("logs", app)
            raise AssertionError(logs.stdout + logs.stderr)
        if not options.expect_dns_failure:
            state = json.loads(docker("inspect", app).stdout)[0]
            logs = docker("logs", app)
            assert state["RestartCount"] == 0
            assert "Traceback" not in logs.stdout + logs.stderr
            assert "Database connection ready." in logs.stdout
            print("PASS: delayed network attachment, migrations, and HTTP 200 without a restart or traceback.", flush=True)
        else:
            print("CONFIRMED: the same container succeeds after network attachment and a second start.", flush=True)
    finally:
        for name in (app, database):
            docker("rm", "-fv", name, check=False)
        for name in (app_network, db_network):
            docker("network", "rm", name, check=False)


if __name__ == "__main__":
    main()
