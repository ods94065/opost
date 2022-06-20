from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from postapi import views as postapi

urlpatterns = [
    path("", postapi.api_root, name="postapi-index"),
    path("boxes", postapi.BoxList.as_view(), name="box-list"),
    path(
        "boxes/<slug:name>",
        postapi.BoxDetail.as_view(),
        name="box-detail",
    ),
    path("posts", postapi.PostList.as_view(), name="post-list"),
    path("posts/<int:pk>", postapi.PostDetail.as_view(), name="post-detail"),
    path(
        "delivered-posts",
        postapi.DeliveredPostList.as_view(),
        name="deliveredpost-list",
    ),
    path(
        "delivered-posts/<int:pk>",
        postapi.DeliveredPostDetail.as_view(),
        name="deliveredpost-detail",
    ),
    path("subscriptions", postapi.SubscriptionList.as_view(), name="subscription-list"),
    path(
        "subscriptions/<int:pk>",
        postapi.SubscriptionDetail.as_view(),
        name="subscription-detail",
    ),
    path("actions/deliver", postapi.deliver, name="deliver-action"),
    path("actions/sync", postapi.sync, name="sync-action"),
    path("users", postapi.UserList.as_view(), name="user-list"),
    path("users/<int:pk>", postapi.UserDetail.as_view(), name="user-detail"),
]

urlpatterns = format_suffix_patterns(urlpatterns)
