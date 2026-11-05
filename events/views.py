from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from jobs.views import require_branch

from .models import Action
from .undo import compensate


@require_POST
def undo(request, event_id):
    branch = require_branch(request)
    action = Action.objects.filter(
        branch=branch, event_id=event_id, device=request.device
    ).first()
    try:
        compensate(
            branch, event_id, request.device, action.staff if action else request.staff
        )
        messages.success(request, "Action undone. History has been preserved.")
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    path = request.POST.get("next", "")
    return redirect(
        path
        if path.startswith(("/jobs/", "/machines/", "/supplies/")) and "\\" not in path
        else "board"
    )
