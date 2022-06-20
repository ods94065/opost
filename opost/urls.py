from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
import rest_framework.urls

admin.autodiscover()

urlpatterns = [
    path(
        "postapi/api-auth/",
        include(rest_framework.urls, namespace="rest_framework"),
    ),
    path("postapi/", include("postapi.urls")),
    path("admin/doc/", include("django.contrib.admindocs.urls")),
    path("admin/", admin.site.urls),
    path("web/", include("postweb.urls", namespace="postweb")),
    path("", RedirectView.as_view(url="/web/")),
]
