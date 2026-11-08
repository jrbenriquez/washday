from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError


def test_waits_for_database_before_allowing_startup():
    database = Mock(vendor="postgresql")
    database.ensure_connection.side_effect = [
        OperationalError("DNS not ready"),
        OperationalError("connection refused"),
        None,
    ]
    output = StringIO()
    with (
        patch("core.management.commands.wait_for_db.connection", database),
        patch("core.management.commands.wait_for_db.time.sleep") as sleep,
    ):
        call_command("wait_for_db", stdout=output)
    assert database.ensure_connection.call_count == 3
    assert database.close.call_count == 3
    assert sleep.call_count == 2
    assert output.getvalue().count("Waiting for database") == 1
    assert "Database connection ready." in output.getvalue()


def test_unavailable_database_fails_startup_without_disclosing_connection_details():
    database = Mock(vendor="postgresql")
    database.ensure_connection.side_effect = OperationalError("private connection details")
    with patch("core.management.commands.wait_for_db.connection", database):
        with pytest.raises(CommandError, match="startup timeout") as error:
            call_command("wait_for_db", timeout=0)
    assert database.ensure_connection.call_count == 1
    assert "private connection details" not in str(error.value)


def test_sqlite_hubs_do_not_wait_for_a_network_database():
    database = Mock(vendor="sqlite")
    with patch("core.management.commands.wait_for_db.connection", database):
        call_command("wait_for_db")
    database.ensure_connection.assert_not_called()
