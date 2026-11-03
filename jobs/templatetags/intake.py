from django import template

register = template.Library()


@register.filter
def piece_qty(data, key):
    return data.get("piece_" + str(key), "0")


@register.filter
def selected(data, pair):
    field, key = pair.split(":", 1)
    return key in (
        data.getlist(field) if hasattr(data, "getlist") else data.get(field, [])
    )


@register.filter
def field_values(data, field):
    return data.getlist(field) if hasattr(data, "getlist") else data.get(field, [])
