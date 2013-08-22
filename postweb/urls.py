from django.conf.urls import patterns, include, url

urlpatterns = patterns('postweb.views',
    url(r'^$', 'index', name='index'),
    url(r'^posts/(?P<pk>.*)$', 'post_detail', name='post-detail'),
    url(r'^compose$', 'compose', name='compose')
)

urlpatterns += patterns('django.contrib.auth.views',
    url(r'^login/$', 'login', name='login'),
    url(r'^logout/$', 'logout_then_login', name='logout'),
)
