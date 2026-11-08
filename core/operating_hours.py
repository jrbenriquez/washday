"""Branch hours for interactive job writes, evaluated using server time."""

from django.core.exceptions import ValidationError
from django.utils import timezone


def require_job_operating_hours(branch):
    opening, closing = branch.opening_time, branch.closing_time
    if opening is None or closing is None:
        raise ValidationError(
            "Ask the owner to set this branch’s opening and closing times before creating or updating jobs."
        )
    now = timezone.localtime(timezone.now()).time()
    if opening == closing:
        return  # Matching times explicitly represent 24-hour operation.
    is_open = (
        opening <= now < closing
        if opening < closing
        else now >= opening or now < closing
    )
    if not is_open:
        raise ValidationError(
            "Jobs can only be created or updated during branch operating hours "
            f"({opening:%H:%M}–{closing:%H:%M}, {timezone.get_current_timezone_name()})."
        )
