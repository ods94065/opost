import urlparse
from django import forms
from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.reverse import reverse
from postapi.models import *
from postapi.serializers import *


@api_view(["GET"])
@permission_classes([])
def api_root(request, format=None):
    """The root resource of the API. Used to navigate the rest of the API."""

    return Response(
        {
            "users": reverse("user-list", request=request, format=format),
            "boxes": reverse("box-list", request=request, format=format),
            "delivered-posts": reverse(
                "deliveredpost-list", request=request, format=format
            ),
            "posts": reverse("post-list", request=request, format=format),
            "subscriptions": reverse(
                "subscription-list", request=request, format=format
            ),
            "actions": {
                "deliver": reverse("deliver-action", request=request, format=format),
            },
        }
    )


class UserList(generics.ListAPIView):
    """Read-only operations on the collection of users."""

    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    """Read-only operations on a specific user."""

    queryset = User.objects.all()
    serializer_class = UserSerializer


class BoxList(generics.ListCreateAPIView):
    """Operations on the collection of boxes."""

    serializer_class = BoxSerializer

    def get_queryset(self):
        queryset = Box.objects.all()
        # Query support for autocompletion of box name
        name_startswith = self.request.QUERY_PARAMS.get("name_startswith", None)
        if name_startswith is not None:
            queryset = queryset.filter(name__istartswith=name_startswith)
        queryset = queryset.order_by("name")
        return queryset


class BoxDetail(generics.RetrieveDestroyAPIView):
    """Operations on an individual box."""

    queryset = Box.objects.all()
    serializer_class = BoxSerializer
    lookup_field = "name"


class PostListForm(forms.Form):
    sender = forms.CharField(required=False)
    start = forms.DateTimeField(required=False)
    end = forms.DateTimeField(required=False)


class PostList(generics.ListCreateAPIView):
    """Operations on the collection of posts."""

    serializer_class = PostSerializer

    def pre_save(self, obj):
        obj.sender = self.request.user

    def get_queryset(self):
        queryset = Post.objects.all()
        form = PostListForm(self.request.QUERY_PARAMS)
        if form.is_valid():
            kwargs = {}
            for field, query_key in [
                ("sender", "sender"),
                ("start", "created__gte"),
                ("end", "created__lte"),
            ]:
                if form.cleaned_data[field]:
                    kwargs[query_key] = form.cleaned_data[field]
            if kwargs:
                queryset = queryset.filter(**kwargs)
        return queryset


class PostDetail(generics.RetrieveDestroyAPIView):
    """Operations on an individual post."""

    queryset = Post.objects.all()
    serializer_class = PostSerializer

    def pre_save(self, obj):
        obj.sender = self.request.user


class DeliveredPostListForm(forms.Form):
    sender = forms.CharField(required=False)
    boxname = forms.CharField(required=False)
    start = forms.DateTimeField(required=False)
    end = forms.DateTimeField(required=False)


class DeliveredPostList(generics.ListCreateAPIView):
    """Operations on the collection of delivered posts."""

    queryset = DeliveredPost.objects.all()
    serializer_class = DeliveredPostSerializer

    def get_queryset(self):
        queryset = DeliveredPost.objects.all()
        form = DeliveredPostListForm(self.request.QUERY_PARAMS)
        if form.is_valid():
            kwargs = {}
            for field, query_key in [
                ("sender", "post_sender"),
                ("boxname", "box__name"),
                ("start", "post_created__gte"),
                ("end", "post_created__lte"),
            ]:
                if form.cleaned_data[field]:
                    kwargs[query_key] = form.cleaned_data[field]
            if kwargs:
                queryset = queryset.filter(**kwargs)
        return queryset


class DeliveredPostDetail(generics.RetrieveUpdateDestroyAPIView):
    """Operations on an individual delivered post."""

    queryset = DeliveredPost.objects.all()
    serializer_class = DeliveredPostSerializer


class SubscriptionList(generics.ListCreateAPIView):
    """Operations on the collection of subscriptions."""

    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer


class SubscriptionDetail(generics.RetrieveUpdateDestroyAPIView):
    """Operations on an individual subscription."""

    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer


@api_view(["POST"])
def deliver(request, format=None):
    """An action that creates a post and immediately delivers it to a set of boxes.

    Inputs:
    - to: a list of box resource URLs (required)
    - subject: a string containing the subject of the message (required)
    - body: a string containing the message to send (required)
    - content_type: the type of content in the body (optional, default='markdown')

    Outputs:
    If there are validation errors, HTTP status code 400, and:
    - non_field_errors: a list of validation error messages not associated with a particular field (optional)
    - to, body, content_type: a list of validation error messages associated with these fields (optional)
    - delivery_errors: errors attempting delivery of the message (optional)
    """

    serializer = DeliverActionSerializer(data=request.DATA)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Create the post.
    data = serializer.object
    post = Post(sender=request.user, subject=data["subject"], body=data["body"])
    # content_type is optional. Only set it if it was specified.
    # Otherwise, let the model choose a default.
    if "content_type" in data:
        post.content_type = data["content_type"]
    post.save()

    # Deliver the posts to the boxes. Collect and return the created DeliveredPost objects.
    dposts = []
    delivery_request_errors = []
    for box in data["to"]:
        dpost, created = DeliveredPost.objects.get_or_create(
            box=box,
            post=post,
            post_sender=request.user,
            post_created=post.created,
            post_subject=post.subject,
        )
        if created:
            dpost_serializer = DeliveredPostSerializer(
                dpost, context={"request": request}
            )
            dposts.append(dpost_serializer.data)

    result = {}
    if len(delivery_request_errors) > 0:
        result["delivery_errors"] = delivery_request_errors
    if len(dposts) > 0:
        result["posts"] = dposts

    return Response({"posts": dposts}, status=status.HTTP_200_OK)


@api_view(["POST"])
def sync(request, format=None):
    """Brings a box up to date with content from all of its subscriptions."""

    serializer = SyncActionSerializer(data=request.DATA)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    box = serializer.object["box"]
    subs = Subscription.objects.filter(target=box)
    for sub in subs:
        source_box = sub.source
        dposts = DeliveredPost.objects.filter(box=source_box).order_by("id")
        if sub.watermark is not None:
            dposts = dposts.filter(id__gt=sub.watermark.id)
        new_watermark = sub.watermark
        for dpost in dposts:
            DeliveredPost.objects.get_or_create(
                box=box,
                post=dpost.post,
                post_sender=dpost.post.sender,
                post_created=dpost.post.created,
                post_subject=dpost.post.subject,
            )
            new_watermark = dpost
        sub.watermark = new_watermark
        sub.save()
    return Response({}, status=status.HTTP_204_NO_CONTENT)
