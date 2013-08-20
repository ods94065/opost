from django.conf.urls import include, patterns, url
from postapi import views
from rest_framework.urlpatterns import format_suffix_patterns

urlpatterns = patterns('postapi.views',
    url(r'^$', 'api_root'),
    url(r'^boxes$', views.BoxList.as_view(), name='box-list'),
    url(r'^boxes/(?P<name>[0-9a-zA-Z-_]+)$', views.BoxDetail.as_view(), name='box-detail'),
    url(r'^posts$', views.PostList.as_view(), name='post-list'),
    url(r'^posts/(?P<pk>[0-9]+)$', views.PostDetail.as_view(), name='post-detail'),
    url(r'^delivered-posts$', views.DeliveredPostList.as_view(),
        name='deliveredpost-list'),
    url(r'^delivered-posts/(?P<pk>[0-9]+)$', views.DeliveredPostDetail.as_view(),
        name='deliveredpost-detail'),
    url(r'^subscriptions$', views.SubscriptionList.as_view(),
        name='subscription-list'),
    url(r'^subscriptions/(?P<pk>[0-9]+)$', views.SubscriptionDetail.as_view(),
        name='subscription-detail'),
    url(r'^actions/deliver', 'deliver', name='deliver-action'),
    url(r'^actions/sync', 'sync', name='sync-action'),
    url(r'^users$', views.UserList.as_view(), name='user-list'),
    url(r'^users/(?P<pk>[0-9]+)$', views.UserDetail.as_view(), name='user-detail'),
)

urlpatterns = format_suffix_patterns(urlpatterns)

urlpatterns += patterns('',
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
)
