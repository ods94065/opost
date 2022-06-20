from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework import serializers
from postapi.models import Box, DeliveredPost, Post, Subscription


class UserSerializer(serializers.HyperlinkedModelSerializer):
    """Translates between the User model and multiple serialized API document formats."""

    class Meta:
        model = User
        fields = ("url", "username")


class BoxSerializer(serializers.HyperlinkedModelSerializer):
    """Translates between the Box model and multiple serialized API document formats."""

    url = serializers.HyperlinkedIdentityField(
        view_name="box-detail", lookup_field="name"
    )
    posts = serializers.HyperlinkedRelatedField(
        many=True, view_name="deliveredpost-detail", read_only=True
    )

    class Meta:
        model = Box
        fields = ("url", "name", "created", "posts")


class PostSerializer(serializers.HyperlinkedModelSerializer):
    """Translates between the Post model and multiple serialized API document formats."""

    sender = serializers.ReadOnlyField(source="sender.username")
    delivered_posts = serializers.HyperlinkedRelatedField(
        view_name="deliveredpost-detail", many=True, read_only=True
    )

    class Meta:
        model = Post
        fields = (
            "url",
            "sender",
            "created",
            "subject",
            "content_type",
            "body",
            "delivered_posts",
        )


class DeliveredPostSerializer(serializers.HyperlinkedModelSerializer):
    """Translates between the DeliveredPost model and multiple serialized API document formats."""

    box = serializers.HyperlinkedRelatedField(
        view_name="box-detail", queryset=Box.objects.all(), lookup_field="name"
    )
    post = serializers.HyperlinkedRelatedField(
        view_name="post-detail", queryset=Post.objects.all()
    )
    delivered = serializers.ReadOnlyField(source="created")
    sender = serializers.ReadOnlyField(source="post_sender.username")
    created = serializers.ReadOnlyField(source="post_created")
    subject = serializers.ReadOnlyField(source="post_subject")

    def update(self, obj, validated_data):
        obj.post_sender = obj.post.sender
        obj.post_created = obj.post.created
        obj.post_subject = obj.post.subject
        return super(DeliveredPostSerializer, self).update(obj, validated_data)

    def create(self, validated_data):
        post = validated_data.get("post")
        return DeliveredPost.objects.create(
            post_sender=post.sender,
            post_created=post.created,
            post_subject=post.subject,
            **validated_data
        )

    class Meta:
        model = DeliveredPost
        fields = (
            "id",
            "url",
            "box",
            "post",
            "created",
            "delivered",
            "is_read",
            "sender",
            "subject",
        )


class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    """Translates between the Subscription model and multiple serialized API document formats."""

    source = serializers.HyperlinkedRelatedField(
        view_name="box-detail", queryset=Box.objects.all(), lookup_field="name"
    )
    target = serializers.HyperlinkedRelatedField(
        view_name="box-detail", queryset=Box.objects.all(), lookup_field="name"
    )
    watermark = serializers.HyperlinkedRelatedField(
        view_name="deliveredpost-detail",
        queryset=DeliveredPost.objects.all(),
        required=False,
    )

    class Meta:
        model = Subscription
        fields = ("url", "source", "target", "created", "watermark")
        read_only_fields = ("created",)


class BoxListField(serializers.Field):
    """A mapping of list-of-box-resources to list-of-box-names."""

    def __init__(self, max_length=None, min_length=None):
        super(BoxListField, self).__init__()
        # a subsidiary field helps us verify and convert every item in the list
        self.converter = serializers.HyperlinkedRelatedField(
            view_name="box-detail", queryset=Box.objects.all(), lookup_field="name"
        )

    def to_internal_value(self, data):
        return [self.converter.to_internal_value(item) for item in data]

    def to_representation(self, value):
        """Convert from list of box URLs to list of box names.

        Like any field, this throws a ValidationError instead of returning values if there are any problems.
        """

        obj = []
        error_messages = []
        for item in value:
            try:
                obj.append(self.converter.to_representation(item))
            except ValidationError as err:
                error_messages.extend(list(err.messages))

        if len(error_messages) > 0:
            raise ValidationError(error_messages)
        else:
            return obj


class DeliverActionSerializer(serializers.Serializer):
    """A special serializer for the 'deliver' action."""

    to = BoxListField(max_length=255)
    content_type = serializers.CharField(required=False)
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()


class SyncActionSerializer(serializers.Serializer):
    """A serializer for the 'sync' action."""

    box = serializers.HyperlinkedRelatedField(
        view_name="box-detail", queryset=Box.objects.all(), lookup_field="name"
    )
