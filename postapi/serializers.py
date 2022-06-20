from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework import serializers
from postapi.models import Box, DeliveredPost, Post, Subscription

class UserSerializer(serializers.HyperlinkedModelSerializer):
    '''Translates between the User model and multiple serialized API document formats.'''
    class Meta:
        model = User
        fields = ('url', 'username')

class BoxSerializer(serializers.HyperlinkedModelSerializer):
    '''Translates between the Box model and multiple serialized API document formats.'''
    posts = serializers.HyperlinkedRelatedField(many=True, view_name="deliveredpost-detail", read_only=True)

    class Meta:
        model = Box
        fields = ('url', 'name', 'created', 'posts')
        lookup_field = 'name'

class PostSerializer(serializers.HyperlinkedModelSerializer):
    '''Translates between the Post model and multiple serialized API document formats.'''
    sender = serializers.Field(source='sender.username')

    class Meta:
        model = Post
        fields = ('url', 'sender', 'created', 'subject', 'content_type', 'body', 'delivered_posts')

class DeliveredPostSerializer(serializers.HyperlinkedModelSerializer):
    '''Translates between the DeliveredPost model and multiple serialized API document formats.'''
    id = serializers.Field(source='id')
    box = serializers.HyperlinkedRelatedField(view_name="box-detail", lookup_field='name')
    post = serializers.HyperlinkedRelatedField(view_name="post-detail")
    delivered = serializers.Field(source='created')
    sender = serializers.Field(source='post_sender')
    created = serializers.Field(source='post_created')
    subject = serializers.Field(source='post_subject')

    def save_object(self, obj, **kwargs):
        obj.post_sender = obj.post.sender
        obj.post_created = obj.post.created
        obj.post_subject = obj.post.subject
        super(DeliveredPostSerializer, self).save_object(obj, **kwargs)

    class Meta:
        model = DeliveredPost
        fields = ('id', 'url', 'box', 'post', 'created', 'delivered', 'is_read', 'sender', 'subject')

class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    '''Translates between the Subscription model and multiple serialized API document formats.'''
    source = serializers.HyperlinkedRelatedField(view_name='box-detail', lookup_field='name')
    target = serializers.HyperlinkedRelatedField(view_name='box-detail', lookup_field='name')
    watermark = serializers.HyperlinkedRelatedField(view_name='deliveredpost-detail', required=False)

    class Meta:
        model = Subscription
        fields = ('url', 'source', 'target', 'created', 'watermark')
        read_only_fields = ('created',)

class BoxListField(serializers.WritableField):
    '''A mapping of list-of-box-resources to list-of-box-names.'''
    def __init__(self, max_length=None, min_length=None):
        super(BoxListField, self).__init__()
        # a subsidiary field helps us verify and convert every item in the list
        self.converter = serializers.HyperlinkedRelatedField(view_name='box-detail', queryset=Box.objects.all(), lookup_field='name')

    def to_native(self, obj):
        return [self.converter.to_native(item) for item in obj]

    def from_native(self, data):
        '''Convert from list of box URLs to list of box names.

        Like any field, this throws a ValidationError instead of returning values if there are any problems.'''
        obj = []
        error_messages = []
        for item in data:
            try:
                obj.append(self.converter.from_native(item))
            except ValidationError as err:
                error_messages.extend(list(err.messages))

        if len(error_messages) > 0:
            raise ValidationError(error_messages)
        else:
            return obj

class DeliverActionSerializer(serializers.Serializer):
    '''A special serializer for the 'deliver' action.'''
    to = BoxListField(max_length=255)
    content_type = serializers.CharField(required=False)
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()

class SyncActionSerializer(serializers.Serializer):
    '''A serializer for the 'sync' action.'''
    box = serializers.HyperlinkedRelatedField(view_name='box-detail', queryset=Box.objects.all(), lookup_field='name')
