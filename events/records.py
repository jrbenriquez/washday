"""The explicit replication/change-journal schema. No arbitrary model loading."""

import json
from datetime import date, datetime, time

from django.apps import apps

OPERATIONAL = (
    "customers.customer",
    "people.device",
    "people.devicesetupcode",
    "people.shift",
    "jobs.job",
    "jobs.jobline",
    "machines.load",
    "supplies.stockcount",
    "supplies.stockcountline",
    "supplies.stockentry",
    "supplies.supplyrequest",
    "catalog.supplytype",
)
CATALOG = (
    "core.settings",
    "core.machinecategory",
    "core.jobstage",
    "catalog.service",
    "catalog.addon",
    "catalog.fee",
    "catalog.pieceitem",
    "catalog.piecevariant",
    "catalog.supplytype",
    "catalog.addonuse",
    "catalog.supplyalias",
    "core.machine",
    "people.staff",
    "people.device",
    "people.devicesetupcode",
)


def model(label):
    if label not in set(
        OPERATIONAL + CATALOG + ("core.branch", "events.event", "events.action")
    ):
        raise ValueError("Unsupported record type")
    return apps.get_model(label)


def fields(instance):
    def encode(value):
        return (
            value.isoformat()
            if isinstance(value, (date, datetime, time))
            else str(value)
        )

    return json.loads(
        json.dumps(
            {
                f.attname: f.value_from_object(instance)
                for f in instance._meta.concrete_fields
            },
            default=encode,
        )
    )


def row(instance):
    return {"model": instance._meta.label_lower, "fields": fields(instance)}
