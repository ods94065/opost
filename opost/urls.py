from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import RedirectView

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^postapi/api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^postapi/', include('postapi.urls')),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^web/', include('postweb.urls', namespace='postweb')),
    url(r'^$', RedirectView.as_view(url='/web/')),
)
