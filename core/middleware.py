from django.conf import settings
from core.models import Branch
from core.tenancy import shop_context
from people.models import Staff


class ShopMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Development-only server configuration. Never read tenant selection from the request.
        request.branch = None
        request.staff = None
        if settings.DEBUG and settings.DEV_BRANCH_ID:
            branch = (
                Branch.unscoped.select_related("shop")
                .filter(pk=settings.DEV_BRANCH_ID)
                .first()
            )
            if branch:
                request.branch = branch
                with shop_context(branch.shop_id):
                    request.staff = (
                        Staff.objects.filter(
                            pk=settings.DEV_STAFF_ID, branch=branch, active=True
                        ).first()
                        if settings.DEV_STAFF_ID
                        else None
                    )
                    return self.get_response(request)
        return self.get_response(request)


def context(request):
    return {
        "branch": getattr(request, "branch", None),
        "app_theme": "dark" if request.COOKIES.get("app_theme") == "dark" else "light",
    }
