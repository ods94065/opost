import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.shortcuts import render, redirect

from postweb.forms import SendMessageForm
from postweb.services import BoxService, PostService
import postweb.utils

logger = logging.getLogger(__name__)


def pprint_json(obj):
    """Pretty-print the given JSON object to a string."""

    return json.dumps(obj, indent=2, separators=(", ", ": "))


@login_required(login_url="/web/login")
def index(request):
    """View messages in the user's mailbox."""

    if request.method == "POST":
        action = request.POST["action"]
        if action == "compose":
            return redirect(reverse("postweb:compose"))

    username = request.user.username

    box_svc = BoxService(request)
    data = {}

    box = box_svc.get_box(username)
    box_created = False
    if not box:
        box = box_svc.create_box(username)
        messages.info(request, f"Created a box for {username}.")

    box_data = pprint_json(box)
    logger.debug(box_data)

    # FIXME: Create a coarse-grained service for retrieving mail from the box.
    # Have that automatically sync the box.
    box_svc.sync(box["url"])

    post_svc = PostService(request)
    dposts = [post_svc.get_delivered_post(post) for post in box["posts"]]
    box_empty = len(dposts) == 0

    post_data = pprint_json(dposts)
    logger.debug(post_data)

    # Convert from service JSON to presentation dictionaries;
    # for now we'll keep this lean and mean.
    for dpost in dposts:
        dpost["detail_url"] = reverse("postweb:post-detail", kwargs={"pk": dpost["id"]})

    data = {
        "username": username,
        "box_created": box_created,
        "box_empty": box_empty,
        "posts": dposts,
    }

    return render(request, "postweb/index.html", data)


@login_required(login_url="/web/login")
def post_detail(request, pk):
    """View a message."""

    if request.method == "POST":
        action = request.POST["action"]
        if action == "delete":
            post_svc = PostService(request)
            post_svc.delete_post(pk)
            return redirect(reverse("postweb:index"))

    post_svc = PostService(request)
    post = post_svc.get_post_detail(pk)

    post_data = pprint_json(post)
    logger.debug(post_data)

    created = postweb.utils.represent_date(post["created"])
    sender = post["sender"]
    subject = post["subject"] or "<No subject>"
    display_headers = [
        {"key": "sent", "value": created},
        {"key": "from", "value": sender},
        {"key": "subject", "value": subject},
    ]

    data = {"post": post, "headers": display_headers}

    return render(request, "postweb/post_detail.html", data)


@login_required(login_url="/web/login")
def compose(request):
    """Compose and send/discard a message."""

    form = None
    if request.method == "POST":
        action = request.POST["action"]
        if action == "cancel":
            messages.info(request, "Message discarded.")
            return redirect(reverse("postweb:index"))
        elif action == "create":
            form = SendMessageForm(request.POST)
            if form.is_valid():
                # FIXME: refactor the box list parsing logic into a custom field.
                box_svc = BoxService(request)
                boxnames = re.split(r"[ ,;] *", form.cleaned_data["send_to"])
                boxes = [box_svc.get_box(name)["url"] for name in boxnames]
                subject = form.cleaned_data["subject"]
                body = form.cleaned_data["body"]
                post_svc = PostService(request)
                post_svc.send_post(boxes, subject, body)

                messages.info(request, "Message sent.")
                return redirect(reverse("postweb:index"))

    if form is None:
        form = SendMessageForm()

    data = {"form": form}
    return render(request, "postweb/compose.html", data)
