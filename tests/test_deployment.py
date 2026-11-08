import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.db import OperationalError


@pytest.mark.django_db
def test_health_checks_database_without_authentication(client):
    assert client.get("/health/").json() == {"status": "ok", "role": "cloud"}
    with patch("config.health.connection.cursor", side_effect=OperationalError("private details")):
        response = client.get("/health/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.parametrize(
    "missing",
    ["DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "PGDATABASE", "PGHOST", "PGUSER", "PGPASSWORD"],
)
def test_cloud_production_rejects_missing_configuration(missing):
    env = {
        **os.environ,
        "DJANGO_DEBUG": "0",
        "APP_ROLE": "cloud",
        "DJANGO_SECRET_KEY": "test-only-secret",
        "DJANGO_ALLOWED_HOSTS": "localhost",
        "PGDATABASE": "test",
        "PGHOST": "localhost",
        "PGUSER": "test",
        "PGPASSWORD": "test-only-password",
    }
    env.pop(missing)
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    expected = "PostgreSQL" if missing == "PGDATABASE" else missing
    assert expected in result.stderr
