from django.contrib import admin

from postapi import models as postapi


@admin.register(postapi.Box)
class BoxAdmin(admin.ModelAdmin):
    pass


@admin.register(postapi.DeliveredPost)
class DeliveredPostAdmin(admin.ModelAdmin):
    pass


@admin.register(postapi.Post)
class PostAdmin(admin.ModelAdmin):
    pass


@admin.register(postapi.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    pass
