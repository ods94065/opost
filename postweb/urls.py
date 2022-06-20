from django.urls import path

from postweb import views as postweb
from django.contrib.auth import views as auth

app_name = "postweb"
urlpatterns = [
    path("", postweb.index, name="index"),
    path("posts/<int:pk>", postweb.post_detail, name="post-detail"),
    path("compose", postweb.compose, name="compose"),
]

urlpatterns += [
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.logout_then_login, name="logout"),
]
