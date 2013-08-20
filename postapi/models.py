from django.db import models

class Box(models.Model):
    '''A mailbox. Broadcasts and groups are also boxes.'''
    created = models.DateTimeField(auto_now_add=True)
    name = models.SlugField(unique=True)

POST_CONTENT_TYPE_CHOICES = (('text/x-markdown', 'Markdown'),)

class Post(models.Model):
    '''A document to be posted to one or more boxes.'''
    created = models.DateTimeField(auto_now_add=True)
    sender = models.ForeignKey('auth.User', related_name='posts')
    subject = models.CharField(max_length=255)
    content_type = models.CharField(choices=POST_CONTENT_TYPE_CHOICES,
                                    default='text/x-markdown',
                                    max_length=63)
    body = models.TextField()

    class Meta:
        ordering = ('created',)

class DeliveredPost(models.Model):
    '''A post delivered to a particular box. These may be marked as read and deleted
    without affecting the underlying post or other boxes.'''
    box = models.ForeignKey('Box', related_name='posts')
    post = models.ForeignKey('Post', related_name='delivered_posts')
    created = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # These are copied from the underlying post:
    # - post_owner and post_subject allow for quick header retrieval.
    # - post_created allows us to sort the mailbox the way you'd expect.
    post_sender = models.ForeignKey('auth.User', related_name='+')
    post_created = models.DateTimeField()
    post_subject = models.CharField(max_length=255)
    
    class Meta:
        # Make sure each message is delivered to the target box at most once!
        unique_together = ('box', 'post')
        ordering = ('post_created',)

class Subscription(models.Model):
    '''Tracks a relationship between boxes, whereby posts delivered to one box will be tracked and delivered to the second.

    This relationship is used to handles broadcasts and group messages.'''
    created = models.DateTimeField(auto_now_add=True)

    # The source is the box we're pulling messages from.
    source = models.ForeignKey('Box', related_name='subscriptions_from')

    # The target is the box we're delivering messages to.
    target = models.ForeignKey('Box', related_name='subscriptions_to')

    # The watermark tracks either the last message we've pulled from the source,
    # OR, if this is a brand-new subscription, it tracks the last post after
    # which our subscription takes effect. If it's null, we will start from the
    # first message delivered to the source box.
    #
    # IMPORTANT: we assume the keys will be monotonically increasing with time!
    watermark = models.ForeignKey('DeliveredPost', blank=True, null=True)
    
    class Meta:
        # Make sure there is at most one subscription between any two boxes!
        unique_together = ('source', 'target')
        ordering = ('created',)
