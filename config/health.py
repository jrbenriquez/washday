from django.http import JsonResponse
from django.conf import settings


def health(request):
    return JsonResponse({'status':'ok','role':settings.APP_ROLE})
