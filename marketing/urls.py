from django.urls import include, path

from config.health import health
from . import views

app_name = "marketing"
public_patterns = [
    path("", views.home, name="home"),
    path("contact/", views.contact, name="contact"),
    path("contact/thanks/", views.thanks, name="thanks"),
]
urlpatterns = [path("health/", health), path("", include((public_patterns, app_name)))]
