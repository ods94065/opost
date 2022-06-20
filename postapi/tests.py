import base64, json, re
import django.test
from postapi.models import Box, DeliveredPost, Post, Subscription
import django.core.exceptions

# Where used, we assume that this ID, regardless of the table, is not present in our test database.
ARBITRARY_NONEXISTENT_ID = 123456
ARBITRARY_NONEXISTENT_NAME = "mxyzptlk"


def papi(resource, key=None):
    """A simple wrapper to simplify URL typing below."""

    if key:
        return f"/postapi/{resource}/{key}"
    else:
        return f"/postapi/{resource}"

def basic_test_auth():
    """Returns the test authentication header value for basic HTTP authentication using the test user."""

    credentials = base64.b64encode(b"test:testy123").strip().decode("utf-8")
    auth_string = f"Basic {credentials}"
    return auth_string


def scrape_pk(url):
    """Given a URL, scrape the primary key of the resource from the URL.

    This is for use when we don't want to exercise the hyperlinking of the API, but we do need to
    know a PK that just got created. We assume the PK is the last path element of the URL passed in,
    and that it is a whole number.
    """

    m = re.search(r"/([0-9]+)$", url)
    if m is None:
        raise ValueError(f"Can't extract primary key from URL: {url}")
    return int(m.group(1))


class JSONClient(django.test.client.Client):
    def _set_json_environ(self, env):
        """Set environment values for JSON request and response."""

        env["content_type"] = "application/json; charset=utf-8"
        env["HTTP_ACCEPT"] = "application/json"

    def _set_json_response(self, response):
        """Parse the response content as a JSON document and store the result as response.json_content."""

        try:
            obj = json.loads(response.content)
        except ValueError:
            obj = None
        response.json_content = obj

    def get(self, path, data={}, **kwargs):
        """Construct a GET request."""

        self._set_json_environ(kwargs)
        # Leave data as-is, since it will go into the query string in this case.
        response = super(JSONClient, self).get(path, data, **kwargs)
        self._set_json_response(response)
        return response

    def post(self, path, data={}, **kwargs):
        """Construct a POST request."""

        self._set_json_environ(kwargs)
        json_data = json.dumps(data)
        response = super(JSONClient, self).post(path, json_data, **kwargs)
        self._set_json_response(response)
        return response

    def put(self, path, data={}, **kwargs):
        """Construct a PUT request."""

        self._set_json_environ(kwargs)
        json_data = json.dumps(data)
        response = super(JSONClient, self).put(path, json_data, **kwargs)
        self._set_json_response(response)
        return response

    def patch(self, path, data={}, **kwargs):
        """Construct a PATCH request."""

        self._set_json_environ(kwargs)
        json_data = json.dumps(data)
        response = super(JSONClient, self).generic("PATCH", path, json_data, **kwargs)
        self._set_json_response(response)
        return response


class AuthAPITestCase(django.test.TestCase):
    """Tests that exercise the API's support for authentiaction."""

    fixtures = ["testuser.json"]

    def test_get_allowed(self):
        """Most GET requests are allowed when authenticated."""

        # Note: It's OK if we get a 404 for some of these... just not a 403!
        for resource in [
            "boxes",
            "posts",
            "delivered-posts",
            "subscriptions",
            "boxes/123",
            "posts/123",
            "delivered-posts/123",
            "subscriptions/123",
        ]:
            r = self.client.get(papi(resource))
            self.assertNotEqual(r.status_code, 403)

    def test_post_forbidden(self):
        """POST requests are forbidden when unauthenticated."""

        for resource in [
            "boxes",
            "posts",
            "delivered-posts",
            "subscriptions",
            "actions/deliver",
        ]:
            r = self.client.post(
                papi(resource), json.dumps({}), content_type="application/json"
            )
            self.assertEqual(r.status_code, 403)

    def test_put_delete_forbidden(self):
        """PUT and DELETE requests are forbidden when unauthenticated."""

        for resource in [
            "boxes/123",
            "posts/123",
            "delivered-posts/123",
            "subscriptions/123",
        ]:
            r = self.client.put(papi(resource), {})
            self.assertEqual(r.status_code, 403)
            r = self.client.delete(papi(resource))
            self.assertEqual(r.status_code, 403)

    def test_basic_auth(self):
        """Basic HTTP authentication works using test user on a sample post."""

        r = self.client.post(
            papi("boxes"), {"name": "foo"}, HTTP_AUTHORIZATION=basic_test_auth()
        )
        self.assertEqual(r.status_code, 201)

    def test_session_auth(self):
        """Django session authentication works using test user on a sample post."""

        self.client.login(username="test", password="testy123")
        r = self.client.post(
            papi("boxes"), json.dumps({"name": "foo"}), content_type="application/json"
        )
        self.assertEqual(r.status_code, 201)
        self.client.logout()


class APITestCase(django.test.TestCase):
    """Tests that ensure the user will be authenticated."""

    fixtures = ["testuser.json"]
    client_class = JSONClient

    def setUp(self):
        self.client.login(
            username="test", password="testy123"
        )  # Constructed to match the fixture data!

    def tearDown(self):
        self.client.logout()


class BoxMixin(object):
    """An APITestCase mixin for creating test boxes.

    This code relies on self.client being a JSONClient.
    """

    def create_box(self, name):
        """Creates a box with the given name and returns its name and URL."""

        r = self.client.post(papi("boxes"), {"name": name})
        self.assertEqual(r.status_code, 201)
        return r.json_content["url"]


class BoxListTestCase(APITestCase, BoxMixin):
    """Tests for /postapi/boxes."""

    def test_create(self):
        """A box can be created with a name."""

        url = self.create_box("foo")
        try:
            # Make sure the object exists in the database.
            self.assertIsNotNone(Box.objects.get(name="foo"))
        except django.core.exceptions.ObjectDoesNotExist:
            self.fail("Recently-created box not in database")
        except django.core.exceptions.MultipleObjectsReturned:
            self.fail("Got more than one box matching the name")

    def test_list(self):
        """Boxes can be listed."""

        self.create_box("owen")
        self.create_box("john")
        r = self.client.get(papi("boxes"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(isinstance(r.json_content, list))
        box_names = [box["name"] for box in r.json_content]
        self.assertCountEqual(box_names, ["owen", "john"])

    def test_list_by_name_startswith(self):
        """Boxes can be listed by just the beginning of a name."""

        self.create_box("annie")
        self.create_box("archie")
        self.create_box("armand")
        self.create_box("bella")
        # check the basics
        r = self.client.get(papi("boxes"), {"name_startswith": "a"})
        self.assertEqual(r.status_code, 200)
        self.assertCountEqual(
            [box["name"] for box in r.json_content], ["annie", "archie", "armand"]
        )
        # check case insensitivity
        r = self.client.get(papi("boxes"), {"name_startswith": "AR"})
        self.assertCountEqual(
            [box["name"] for box in r.json_content], ["archie", "armand"]
        )
        # check queries with no results
        r = self.client.get(papi("boxes"), {"name_startswith": "c"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json_content, [])

    def test_fails_if_added_twice(self):
        """Adding a box with the same name twice is illegal."""

        r = self.client.post(papi("boxes"), {"name": "foo"})
        self.assertEqual(r.status_code, 201)
        r = self.client.post(papi("boxes"), {"name": "foo"})
        self.assertEqual(r.status_code, 400)


class BoxDetailTestCase(APITestCase, BoxMixin):
    """Tests for /postapi/boxes/<pk>."""

    def setUp(self):
        super(BoxDetailTestCase, self).setUp()
        self.name = "mannie"
        self.create_box(self.name)

    def test_get(self):
        """A box's details may be retrieved."""

        r = self.client.get(papi("boxes", self.name))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json_content["name"], self.name)

    def test_put_and_patch_fail(self):
        """A box's details may not be modified."""

        r = self.client.put(papi("boxes", self.name), {"name": "moe"})
        self.assertEqual(r.status_code, 405)
        r = self.client.patch(papi("boxes", self.name), {"name": "moe"})
        self.assertEqual(r.status_code, 405)

    def test_get_fails_if_not_present(self):
        """Box detail gives a 404 if the box isn't present."""

        r = self.client.get(papi("boxes", ARBITRARY_NONEXISTENT_NAME))
        self.assertEqual(r.status_code, 404)


class PostMixin(object):
    """An APITestCase mixin for creating test posts.

    This code relies on self.client being a JSONClient.
    """

    def create_post(self, subject, body):
        """Creates a box with the given name and returns its PK."""

        r = self.client.post(papi("posts"), {"subject": subject, "body": body})
        self.assertEqual(r.status_code, 201)
        url = r.json_content["url"]
        return (scrape_pk(url), url)


class PostListTestCase(APITestCase, PostMixin):
    """Tests for /postapi/posts."""

    def test_create(self):
        """A post can be created with a body."""

        pk, url = self.create_post("Test", "Hello, world!")
        try:
            # Make sure the object exists in the database.
            self.assertIsNotNone(Post.objects.get(id=pk))
        except django.core.exceptions.ObjectDoesNotExist:
            self.fail("Recently-created post not in database")

    def test_list(self):
        """Posts can be listed."""

        self.create_post("Test", "Hello, there!")
        self.create_post("Test 2", "Hi yourself.")
        r = self.client.get(papi("posts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(isinstance(r.json_content, list))
        posts = [post["body"] for post in r.json_content]
        self.assertCountEqual(posts, ["Hello, there!", "Hi yourself."])


class PostDetailTestCase(APITestCase, PostMixin):
    """Tests for /postapi/posts/<pk>."""

    def setUp(self):
        super(PostDetailTestCase, self).setUp()
        self.pk, _ = self.create_post("Beginning", "Call me Ishmael.")

    def test_get(self):
        """A post's details may be retrieved."""

        r = self.client.get(papi("posts", self.pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json_content["subject"], "Beginning")
        self.assertEqual(r.json_content["body"], "Call me Ishmael.")

    def test_put(self):
        """A post's details may not be modified."""

        r = self.client.put(
            papi("posts", self.pk), {"subject": "Epilogue", "body": "The drama's done."}
        )
        self.assertEqual(r.status_code, 405)

    def test_patch(self):
        """A post's details may not be partially updated."""

        r = self.client.patch(papi("posts", self.pk), {"subject": "Epilogue"})
        self.assertEqual(r.status_code, 405)

    def test_get_fails_if_not_present(self):
        """Post detail gives a 404 if the box isn't present."""

        r = self.client.get(papi("posts", ARBITRARY_NONEXISTENT_ID))
        self.assertEqual(r.status_code, 404)


class DeliveredPostMixin(BoxMixin, PostMixin):
    """An APITestCase mixin for creating delivered posts."""

    class Data(object):
        def __init__(self, box_name, box_url, post_pk, post_url, dpost_pk, dpost_url):
            self.box_name = box_name
            self.box_url = box_url
            self.post_pk = post_pk
            self.post_url = post_url
            self.dpost_pk = dpost_pk
            self.dpost_url = dpost_url

    def deliver_post(self, box_url, post_url):
        r = self.client.post(
            papi("delivered-posts"), {"box": box_url, "post": post_url}
        )
        self.assertEqual(r.status_code, 201)
        url = r.json_content["url"]
        return (scrape_pk(url), url)

    def create_and_deliver_post(self, boxname, subject, body):
        box_url = self.create_box(boxname)
        post_pk, post_url = self.create_post(subject, body)
        dpost_pk, dpost_url = self.deliver_post(box_url, post_url)
        return DeliveredPostMixin.Data(
            boxname, box_url, post_pk, post_url, dpost_pk, dpost_url
        )


class DeliveredPostListTestCase(APITestCase, DeliveredPostMixin):
    """Tests for /postapi/delivered-posts."""

    def test_create(self):
        """A post can be delivered."""

        data = self.create_and_deliver_post("john", "Test", "Hello, world!")
        try:
            # Make sure the object exists in the database.
            dpost = DeliveredPost.objects.get(id=data.dpost_pk)
            self.assertIsNotNone(dpost)

        except django.core.exceptions.ObjectDoesNotExist:
            self.fail("Recently-created post not in database")

    def test_fails_if_delivered_twice(self):
        """At most one instance of a post may be delivered to a box at a time."""

        box_url = self.create_box("foo")
        _, post_url = self.create_post("Test", "Hello, world!")
        r = self.client.post(
            papi("delivered-posts"), {"box": box_url, "post": post_url}
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.post(
            papi("delivered-posts"), {"box": box_url, "post": post_url}
        )
        self.assertEqual(r.status_code, 400)

        # ...however, this counts as a separate post!
        _, post_url2 = self.create_post("Test", "Hello, world!")
        r = self.client.post(
            papi("delivered-posts"), {"box": box_url, "post": post_url2}
        )
        self.assertEqual(r.status_code, 201)

    def test_list(self):
        """Delivered posts can be listed."""

        self.create_and_deliver_post("john", "Test", "Hello, world!")
        self.create_and_deliver_post("owen", "Test 2", "Hello again.")
        r = self.client.get(papi("delivered-posts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(isinstance(r.json_content, list))
        posts = [delivered_post["subject"] for delivered_post in r.json_content]
        self.assertCountEqual(posts, ["Test", "Test 2"])

    def test_list_by_sender(self):
        """Delivered posts can be filtered by sender."""

        self.create_and_deliver_post("john", "Test", "Hello, world!")
        self.create_and_deliver_post("owen", "Test 2", "Hello again.")
        r = self.client.get(papi("delivered-posts"), {"boxname": "owen"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(isinstance(r.json_content, list))
        posts = [delivered_post["subject"] for delivered_post in r.json_content]
        self.assertCountEqual(posts, ["Test 2"])


class DeliveredPostDetailTestCase(APITestCase, DeliveredPostMixin):
    """Tests for /postapi/delivered-posts/<pk>."""

    def setUp(self):
        super(DeliveredPostDetailTestCase, self).setUp()
        self.data = self.create_and_deliver_post("john", "Test", "Hello, world!")

    def test_get(self):
        """A delivered post's details may be retrieved."""

        r = self.client.get(papi("delivered-posts", self.data.dpost_pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json_content["box"], self.data.box_url)
        self.assertEqual(r.json_content["post"], self.data.post_url)
        self.assertIn("created", r.json_content)
        self.assertIn("delivered", r.json_content)
        self.assertFalse(r.json_content["is_read"])
        self.assertEqual(r.json_content["sender"], "test")
        self.assertEqual(r.json_content["subject"], "Test")

    def test_mark_read_and_unread(self):
        """Delivered posts may be marked read and unread, and are unread by default."""

        # default is unread
        self.assertFalse(DeliveredPost.objects.get(id=self.data.dpost_pk).is_read)

        # mark as read
        r = self.client.patch(
            papi("delivered-posts", self.data.dpost_pk), {"is_read": True}
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(DeliveredPost.objects.get(id=self.data.dpost_pk).is_read)

        # now mark as unread again
        r = self.client.patch(
            papi("delivered-posts", self.data.dpost_pk), {"is_read": False}
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(DeliveredPost.objects.get(id=self.data.dpost_pk).is_read)

    def test_delete(self):
        """Delivered posts can be deleted without affecting the underlying post."""

        r = self.client.delete(papi("delivered-posts", self.data.dpost_pk))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(DeliveredPost.objects.filter(id=self.data.dpost_pk).exists())
        self.assertTrue(Post.objects.filter(id=self.data.post_pk).exists())

    def test_get_fails_if_not_present(self):
        """Delivered post detail gives a 404 if the box isn't present."""

        r = self.client.get(papi("delivered-posts", ARBITRARY_NONEXISTENT_ID))
        self.assertEqual(r.status_code, 404)


class SubscriptionMixin(DeliveredPostMixin):
    """An APITestCase mixin for creating test subscriptions.

    This code relies on self.client being a JSONClient.
    """

    class Data(object):
        def __init__(
            self, source_name, source_url, target_name, target_url, sub_pk, sub_url
        ):
            self.source_name = source_name
            self.source_url = source_url
            self.target_name = target_name
            self.target_url = target_url
            self.sub_pk = sub_pk
            self.sub_url = sub_url

    def create_subscription(self, source_url, target_url):
        """Creates a subscription with the given source and target, and returns its PK and URL."""

        r = self.client.post(
            papi("subscriptions"), {"source": source_url, "target": target_url}
        )
        self.assertEqual(r.status_code, 201)
        url = r.json_content["url"]
        return (scrape_pk(url), url)

    def create_boxes_and_subscription(self, source_name, target_name):
        """Creates two boxes with the given names and creates a subscription between them.

        Returns a struct containing source, target, and subscription PKs and URLs.
        """

        source_url = self.create_box(source_name)
        target_url = self.create_box(target_name)
        sub_pk, sub_url = self.create_subscription(source_url, target_url)
        return SubscriptionMixin.Data(
            source_name, source_url, target_name, target_url, sub_pk, sub_url
        )


class SubscriptionListTestCase(APITestCase, SubscriptionMixin):
    """Tests for /postapi/subscriptions."""

    def test_create(self):
        """A subscription can be created."""

        data = self.create_boxes_and_subscription("everyone", "john")
        try:
            # Make sure the object exists in the database.
            sub = Subscription.objects.get(id=data.sub_pk)
            self.assertIsNotNone(sub)
        except django.core.exceptions.ObjectDoesNotExist:
            self.fail("Recently-created post not in database")

    def test_list(self):
        """Subscriptions can be listed."""

        data1 = self.create_boxes_and_subscription("everyone", "owen")
        data2 = self.create_boxes_and_subscription("group1", "john")
        r = self.client.get(papi("subscriptions"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(isinstance(r.json_content, list))
        sources = [sub["source"] for sub in r.json_content]
        self.assertCountEqual(sources, [data1.source_url, data2.source_url])

    def test_fails_if_delivered_twice(self):
        """At most one subscription may exist between a given source and target."""

        source_url = self.create_box("everyone")
        target_url = self.create_box("john")
        r = self.client.post(
            papi("subscriptions"), {"source": source_url, "target": target_url}
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.post(
            papi("subscriptions"), {"source": source_url, "target": target_url}
        )
        self.assertEqual(r.status_code, 400)


class SubscriptionDetailTestCase(APITestCase, SubscriptionMixin):
    """Tests for /postapi/subscriptions/<pk>."""

    def setUp(self):
        super(SubscriptionDetailTestCase, self).setUp()
        self.data = self.create_boxes_and_subscription("everyone", "john")

    def test_get(self):
        """A subscription's details may be retrieved."""

        r = self.client.get(papi("subscriptions", self.data.sub_pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json_content["source"], self.data.source_url)
        self.assertEqual(r.json_content["target"], self.data.target_url)
        self.assertIsNone(r.json_content["watermark"])
        self.assertIn("created", r.json_content)

    def test_set_watermark(self):
        """A subscription's watermark may be modified via a patch."""

        _, post_url = self.create_post(
            "Emergency", "This is a test of the emergency broadcast system."
        )
        dpost_pk, dpost_url = self.deliver_post(self.data.source_url, post_url)
        r = self.client.patch(
            papi("subscriptions", self.data.sub_pk), {"watermark": dpost_url}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            Subscription.objects.get(id=self.data.sub_pk).watermark.id, dpost_pk
        )

    def test_delete(self):
        """A subscription may be deleted."""

        r = self.client.delete(papi("subscriptions", self.data.sub_pk))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Subscription.objects.filter(id=self.data.sub_pk).exists())

    def test_get_fails_if_not_present(self):
        """Subscription detail gives a 404 if the subscription isn't present."""

        r = self.client.get(papi("subscriptions", ARBITRARY_NONEXISTENT_ID))
        self.assertEqual(r.status_code, 404)


class DeliverActionTestCase(APITestCase, BoxMixin):
    """Tests for /actions/deliver."""

    def setUp(self):
        super(DeliverActionTestCase, self).setUp()
        self.box_url = self.create_box("mannie")

    def test_one(self):
        """Delivery of a message to one box works."""

        r = self.client.post(
            papi("actions/deliver"),
            {"to": [self.box_url], "subject": "Test", "body": "Hello, world!"},
        )
        self.assertEqual(r.status_code, 200)
        dposts = r.json_content["posts"]
        self.assertEqual(len(dposts), 1)
        dpost_pk = scrape_pk(dposts[0]["url"])
        dpost = DeliveredPost.objects.get(id=dpost_pk)
        self.assertIsNotNone(dpost)
        self.assertEqual(dpost.post.body, "Hello, world!")

    def test_multiple(self):
        """Delivery of a message to multiple boxes works."""

        box_url2 = self.create_box("moe")
        r = self.client.post(
            papi("actions/deliver"),
            {
                "to": [self.box_url, box_url2],
                "subject": "Test",
                "body": "Hello, world!",
            },
        )
        self.assertEqual(r.status_code, 200)
        dposts = r.json_content.get("posts", [])
        self.assertEqual(len(dposts), 2)
        for pk in [scrape_pk(dpost_data["url"]) for dpost_data in dposts]:
            dpost = DeliveredPost.objects.get(id=pk)
            self.assertIsNotNone(dpost)
            self.assertEqual(dpost.post.body, "Hello, world!")

    def test_fails_if_box_not_present(self):
        """Delivery of a message to a nonexistent box fails."""

        r = self.client.post(
            papi("actions/deliver"),
            {
                "to": [f"http://localserver/boxes/{ARBITRARY_NONEXISTENT_NAME}"],
                "subject": "Test",
                "body": "Hello, world!",
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_succeds_if_box_listed_twice(self):
        """Delivery succeeds even if the same box is listed multiple times."""

        r = self.client.post(
            papi("actions/deliver"),
            {
                "to": [self.box_url, self.box_url],
                "subject": "Test",
                "body": "Hello, world!",
            },
        )
        self.assertEqual(r.status_code, 200)
        # Ensure we did just one delivery, and that it is reported here.
        dposts = r.json_content.get("posts", [])
        self.assertEqual(len(dposts), 1)
        dpost = DeliveredPost.objects.get(id=scrape_pk(dposts[0]["url"]))
        self.assertIsNotNone(dpost)
        self.assertEqual(dpost.post.body, "Hello, world!")


class SyncActionTestCase(APITestCase, SubscriptionMixin):
    """Tests for /actions/sync."""

    def setUp(self):
        super(SyncActionTestCase, self).setUp()
        self.data = self.create_boxes_and_subscription("cool-people", "mannie")

    def test_no_watermark(self):
        """Sync works with no previous watermark."""

        post_pk, post_url = self.create_post("Test", "Hello, cool people!")
        dpost_pk, _ = self.deliver_post(self.data.source_url, post_url)
        sub = Subscription.objects.get(id=self.data.sub_pk)
        self.assertIsNone(sub.watermark)
        self.assertEqual(
            DeliveredPost.objects.filter(box__name=self.data.target_name).count(), 0
        )
        r = self.client.post(papi("actions/sync"), {"box": self.data.target_url})
        self.assertEqual(r.status_code, 204)
        sub = Subscription.objects.get(id=self.data.sub_pk)
        self.assertEqual(sub.watermark.id, dpost_pk)
        dposts = list(DeliveredPost.objects.filter(box__name=self.data.target_name))
        self.assertEqual(len(dposts), 1)
        self.assertEqual(dposts[0].post.id, post_pk)

    def test_with_watermark(self):
        """Sync works with a previous watermark."""

        # Initial setup: two posts delivered to the source mailbox,
        # with the first also delivered to the target mailbox,
        # and the watermark set to the first delivered post.
        posts = [
            self.create_post("Test", "Hello, cool people!"),
            self.create_post(
                "Free Trashcan Mac offer for cool people only", "Made you look!"
            ),
        ]
        source_dposts = [
            self.deliver_post(self.data.source_url, post_data[1]) for post_data in posts
        ]
        self.deliver_post(self.data.target_url, posts[0][1])
        r = self.client.patch(
            papi("subscriptions", self.data.sub_pk), {"watermark": source_dposts[0][1]}
        )
        self.assertEqual(r.status_code, 200)
        sub = Subscription.objects.get(id=self.data.sub_pk)
        self.assertEqual(sub.watermark.id, source_dposts[0][0])

        # Test: sync delivers the second post and updates the watermark.
        r = self.client.post(papi("actions/sync"), {"box": self.data.target_url})
        self.assertEqual(r.status_code, 204)
        sub = Subscription.objects.get(id=self.data.sub_pk)
        self.assertEqual(sub.watermark.id, source_dposts[1][0])
        dposts = list(DeliveredPost.objects.filter(box__name=self.data.target_name))
        self.assertEqual(len(dposts), 2)
        self.assertEqual(dposts[1].post.id, posts[1][0])
