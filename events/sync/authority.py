from django.conf import settings
from django.core.exceptions import ValidationError

from events.models import Replica


def assert_writer(branch):
    if settings.APP_ROLE == "cloud":
        if branch.mode != "direct":
            raise ValidationError("This branch is served by its hub.")
    elif (
        str(branch.pk) != str(settings.HUB_BRANCH_ID)
        or branch.mode != "hub"
        or not Replica.objects.filter(
            branch=branch, writer_active=True, frozen=False
        ).exists()
    ):
        raise ValidationError(
            "This hub is not the active writer. Finish bootstrap or mode migration first."
        )
