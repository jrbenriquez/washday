from django.conf import settings
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe, require_http_methods

from .forms import InquiryForm, submission_token
from .models import Inquiry


def context(**extra):
    return {
        "app_login_url": settings.MARKETING_APP_LOGIN_URL,
        "intro_video_url": settings.MARKETING_VIDEO_URL or static("marketing/washday-commercial.mp4"),
        **extra,
    }


@require_safe
def home(request):
    return render(request, "marketing/home.html", context())


@never_cache
@require_http_methods(["GET", "POST"])
def contact(request):
    kind = request.GET.get("type", Inquiry.Type.DEMO)
    if kind not in Inquiry.Type.values:
        kind = Inquiry.Type.DEMO
    form = InquiryForm(
        request.POST if request.method == "POST" else None,
        initial={"type": kind, "submission_token": submission_token()},
    )
    if request.method == "POST" and form.is_valid():
        values = {key: form.cleaned_data[key] for key in form.Meta.fields}
        if values["type"] == Inquiry.Type.CUSTOM:
            values.update(branch_count=None, availability="")
        # A browser retry creates one record, even across workers.
        record, _ = Inquiry.objects.get_or_create(submission_id=form.submission_id, defaults=values)
        request.session["marketing_inquiry_type"] = record.type
        return redirect("marketing:thanks")
    return render(request, "marketing/contact.html", context(form=form))


@never_cache
@require_safe
def thanks(request):
    kind = request.session.get("marketing_inquiry_type")
    if kind not in Inquiry.Type.values:
        return redirect("marketing:contact")
    return render(request, "marketing/thanks.html", context(is_demo=kind == Inquiry.Type.DEMO))
