# Opost: a proof-of-concept mail system

This is a sample project to show a basic two-tiered mail delivery and
viewing system. It was done over two weekends: one many years ago
as a coding challenge; more recently a weekend spent porting to the
latest and greatest versions of Django and Django REST framework (which
have changed pretty substantially). It's been fun to reflect on how
much I've learned about Python web applications and deployment since
that initial challenge.

## User Requirements

- Can send email from one person to another.
- Can view, mark as read, and delete messages.
- Messages are created in Markdown format, but are formatted into HTML
  for display.
- Can broadcast messages to all users efficiently.
- Can send messages to large gropus of users efficiently.
- A user who belongs to a group only sees messages from the time when
  they joined the group.

## How to use

### System Requirements

A system wtih PostgreSQL (or access to a PostgreSQL database) and Python
3.8 or better.

### Setting Up the Project

1. Create a Python virtual environment for sanity (e.g. with
   `/path/to/my/python3 -m venv venv`), activate it,
   (e.g. with `. venv/bin/activate`), and install the application
   requirements with `pip install -r requirements.txt`.
2. Make sure you have a Postgres database running – on my desktop
   I use Postgres in a Docker container. Create a database for the
   application by e.g. logging into `psql` and using
   `CREATE DATABASE opost`.
3. Create a `.env` file in the top-level project directory with the
   following values:
   - `DATABASE_URL=postgres://...`, filling in the connection
     parameters for the Postgres database you have set up. E.g. for
     my database in Docker, it's
     `postgres://postgres:postgrespw@localhost:7000/opost`.
   - `DEBUG=true` (this would be `false` in production)
   - `SECRET_KEY=this-is-a-dummy-key` (this would be replaced with
      an actual Django secret in production)
4. Run `python manage.py migrate` to apply Django's models to the
   database and create all the necessary tables.
5. Run `python manage.py loaddata auth`. This adds two users to the
   database:
   - Superuser `udapost`, password `admin123`
   - User `test`, password `deadbeef`
6. Run `python manage.py loaddata boxes`. This creates mailboxes for
   the users created above.

### Running the App

7. Run `python manage.py runserver localhost:5100`. (There is one
   place in the code you'll want to adjust if you choose to run on a
   different host/port.)
8. Point your browser at http://localhost:5100 .

### Testing

These tests require a database to connect to. They create a separate
test database, and scrub the database automatically after the tests
are done.

1. Follow steps 1-4 above to set up the database.
2. Run `python manage.py test`.

## Approach

Since this project is a coding challenge, we will set aside questions
about whether an off-the-shelf mail system would be a better solution. We
are also putting aside things like compatibility with existing mail
services and interfaces (but see _Future Directions_ below).

### Data and Domain Design

The starting points for domain analysis are the message, mailbox, and
mail user, represented by the domain models Box, Post, and User,
respectively.

![Fig. 1: Entity-Relationship Diagram](er.png "E-R Diagram")

#### User

For purposes of this project, we will simply use Django's built-in
User model. It consists of a username and password, among other
things, and is tied into Django's auth & auth framework.

#### Box

A box consists of a name and a time that the box was created. Each
user will have a box that corresponds to their username. In addition,
we will reserve a box called 'everyone' that is used for broadcasts,
and each group will have a box associated with it as well. This
ensures that the delivery mechanism will be identical whether we are
sending to a user's mailbox, multicasting to a group, or broadcasting.

#### Post and DeliveredPost

The key to achieving efficient broadcast and messages is not having to
copy the entire message to enormous numbers of mailboxes when sending
the message. Indeed, if broadcasts and groups are frequently enough
used, and we are able to avoid copies of message data altogether,
storing only one copy of the message body would be a signifcant
storage savings win for the mail system!

Therefore, I split the concept of Post into two separate models: Post
and DeliveredPost.

- Post tracks the data that's common to the post, no matter whose
  mailbox it ends up in: the time the post was created, the sender,
  the subject, and the body.
- DeliveredPost tracks the details of the post as it exists in
  someone's Box: whether that post has been read, and when it was
  delivered.

There is a one-to-many correspondence between Box and DeliveredPost
(each box may have multiple posts delivered to it), and a further
one-to-many correspondence between Post and DeliveredPost (each post
may be delivered to multiple boxes).

Users can delete DeliveredPosts from their Box. In this case, the
underlying Post will _not_ be deleted, so that it may still be viewed
by other users. Posts that are no longer referenced by any
DeliveredPost may be reaped in a background or scheduled maintenance
process. Alternatively, they may be archived if desired.

For efficiency in querying the mailbox, I store some of the Post
fields as duplicate fields in DeliveredPost. The disadvantage is that
these fields must be kept in sync. To mitigate this, we will not allow
posts to be edited once they are posted.

#### Subscription

To get broadcast messages from the broadcast box to individual users,
I choose to model a unidirectional relationship between boxes that
will indicate that messages sent to one box (called the source) should
also be delivered to the second (called the target). More precisely:
any DeliveredPost in the source Box, if it falls under the purview of
a Subscription, will give rise to the creation of a corresponding
DeliveredPost in the target. The two DeliveredPost objects will
reference the same Post.

To make sure we only see posts from when we joined a group, and also
to make sure that posts only get processed and delivered once, each
subscription shall keep track of a watermark that records the _last_
post that was processed from the source to the target. There are three
cases here to consider:

- We create the subscription, but there are no messages in the source
  mailbox. In this case, the watermark is set to null. This ensures
  that we will fetch all DeliveredPosts that appear in the source box and
  deliver them to the destination.
- When we create the subscription, there are messages in the source
  mailbox. In this case, the watermark is set to the DeliveredPost in
  the source mailbox at the time the subscription was
  created. This ensures that only messages _after_ the subscription
  began will be delivered.
- The subscription is active, and one or more posts have been delivered
  through the subscription. In this case, the watermark is set to the last
  DeliveredPost in the source whose underlying Post was also delivered
  to the target.

Note that, instead of using timestamps for the watermark (which can
admit of inexactitude through clock drift and other issues), we use
the ID of the DeliveredPost directly. The big assumption here is that
these IDs will be monotonically increasing over time! Fortunately, the
database sequence used to generate IDs does have this behavior.

Also note that using a watermark only works if DeliveredPosts are
processed in strict order of ascending ID, and none are skipped.
Ordering is easy to guarantee, and skipping is not an issue for the
proof of concept. However, in a more robust mail system, we might have
to address cases where a post cannot be delivered at a particular
point in time. Rather than aborting the subscription processing
altogether, if only an isolated message is the probelem, we might push
it onto a retry queue, deferring its delivery, and then skip it for
further subscription processing. The retry in this case would have to
be handled outside of the subscription.

The advantage of using Subscriptions is that broadcasts and group
multicasts are very fast (we just deliver to the source box), and the
delivery to the target can be deferred all the way to when the target
box's mail is actually retrieved. Thus, fallow users in the system
will not result in mail delivery resources being consumed unless we
want them to. The watermark, which at first tracks when a user started
subscribing to a group, meets a requirement that would otherwise be
very difficult to reconcile with the decoupling of brooadcast/group
posting and subscription delivery.

The disadvantages to this model are:

- Every user box must subscribe to the 'everyone' box, thus ensuring
  that the number of Subscription objects is at least as big as the
  size of Box objects. However, subscriptions are relatively cheap:
  100M users will result in perhaps 1.6GB of subscription records just
  for the 'everyone' box. (That's counting 16 bytes per record, not
  counting indices on source and target.) It's unlikely that 1.6GB is
  going to cause significant storage issues with modern storage
  hardware.
- If mail is only pulled from the subscription when the target is
  accessed, some box retrieval operations could be very expensive,
  because they may have a lot of undelivered messages to retrieve
  first. To mitigate this, see _Future Directions_.

### System Architecture

The system is implemented as a single web service, implementing both
an API layer and a front-end layer, and a relational database.

By exposing the back-end API as an independent and complete platform,
we gain several benefits:

- We ensure that different UIs can be plugged into the same back end
  (e.g. mobile, web, desktop, or unexpected new applications), avoiding
  repeated business logic.
- We ensure that the complete set of message data is within the grasp
  of a power user or service provider if they desire to migrate mail
  to another system, or create backups. (This is a major flaw with
  several existant mail providers.)

PostgreSQL is being used for the database. Performance should be more
than suitable for a small web application, but these days I would have
my eye on Cassandra for larger OLTP applications that need more
reliability and handle larger volume.

### Application Architecture

Both the front-end and back-end are implemented in Python and Django,
a language and framework I am already familiar with.

I have used the Django REST framework on top of Django to simply the
development of the back-end API. It handles multiple API input/output
formats (JSON is the main one used in this proof of concept), as well
as the common CRUD patterns associated with REST APIs, and support for
hyperlinking and a browsable API through HTML, which are nice advanced
touches that many so-called REST APIs cannot deliver.

The disadvantages of this stack are:

- Web applications are frequently writen these days as primarily
  Javascript applications using e.g. React. The approach here, which
  drives almost the entire front end through Django and templates, is
  a bit fustier, but still viable for many web applications.
- Python is not a particularly fast language; scaling a web application
  in Python can be expensive and has limits.

### API Design

All API calls are implemented under the '/postapi/' URL space. For the
most part, the API is implemented in what has become a standard
RESTful approach. Take, for example, Post, which has a corresponding
collection resource called `posts`:

- `GET /postapi/posts` retrieves a list of post resource descriptions,
  and can accept query strings such as `start=<date>`.
- `POST /postapi/posts` creates a new post.
- `GET /postapi/posts/<id>` retrieves an individual post record, and
  this URL is the canonical way of identifying the post in all API
  responses.
- `PUT /postapi/posts/<id>` would completely replaces the contents of
  the given post. However, it's disabled for this particular resource
  collection.
- `PATCH /postapi/posts/<id>` allow partial update of the given post,
  by specifying a JSON document that only contains the fields that
  need updating. This, too, is disabled for this particular resource
  collection.
- `DELETE /postapi/posts/<id>` deletes the given post. In this
  particular case, it will cascade to delete any DeliveredPosts that
  reference this post.

This pattern is replicated with the collections `boxes`, `users`,
`delivered-posts`, and `subscriptions`. In addition, the following
methods are globally available:

- `HEAD <url>` gives high-level information about the resource
  available at this URL, including information about what HTTP methods
  are allowed on the URL.
- `OPTIONS <url>` gives detailed information about the resource
  available at this URL, including a description, and acceptable
  input/output formats.

There are two coarse-grained operations that I chose to make POSTable
actions instead of managing them as resource collections:

- `POST /postapi/actions/deliver` is a combined set of actions that create and
  deliver a single post to a list of boxes.
- `POST /postapi/actions/sync` is an action that takes a box and fetches all
  posts from subscriptions targeting that box.

## Future Directions

_Testing:_ Much more edge-case testing needs to be introduced. We are
also missing testing for less common HTTP methods like OPTIONS and
HEAD. We are also missing user acceptance tests, which should probably
be written with the web user in mind, and use Selenium or something
equivalent.

_Telemetry:_ Logging, APM, and error alerts are nigh essential to
a production web application deployment, and are all pretty much
nonexistent here. There's a nod to logging, and a rudimentary
email-on-error facility suggested by the logs, but a better approach
would be to use e.g. Datadog for centralized collection of logs,
metrics, and APM, and driving alerting through e.g. PagerDuty.

_HTTPS:_ A secure channel to the API is important to protect passwords
in the case where basic HTTP authorization is used. It also helps
ensure that message contents remain private.

_Auth & Auth:_ The proof of concept system is very permissive,
allowing users to delete anybody's box or posts, for example. More
could be done within Django's built-in auth system. However, drop-
in third-party auth & auth services should be investigated as well,
so long as budget and security policies permit.

_L10N and I18N:_ The front end needs to have localized strings. We
might want date formats in the front-end to vary depending on the
user's country and preference. In the API, however, I recommend
sticking with ISO-8601.

_Vertical service scaling:_ Right now, for convenience, both the API
service and the front-end service are implemented in the same Django
instance. Since they are implemented as independent Django
applications, they could be easily split out to separate, independent
Django instances, even running on different systems, so that they may
be scaled independently.

_Edge caching:_ No edge cache for web pages or assets has been
established, so performance globally will be slow and perhaps a bit
unreliable. In addition to cloud provider edge caches, CloudFlare
and Akamai could be considered here.

_Horizontal service scaling:_ REST API and HTTP services are easy to
scale by lining up multiple instances of the web application on
different systems (or, in the case of Heroku and OpenShift, different
lightweight containers on systems). A load balancer is used to
distribute load among the instances. SSL may be terminated at the load
balancer.

_Horizontal data scaling:_ Many mail systems partition users and
mailboxes up into different systems and databases. This poses several
problems:
- We need to consider the case where posts are created in different
  shards than the boxes they are delivered to. One possible solution
  to this would be to distribute posts to _all_ of the shards
  they need to be delivered to, so that local joins still work – but
  this could greatly complicate the editing of posts. Some sort of
  eventually-consistent and reliable update across databases would
  need to be devised. Another possibility: avoid the copy and just
  replace joins with URLs to the post where it lives (i.e. "only
  deliver pointers") – but this will cost an extra service call to
  fetch the post contents, and across datacenters and regions this
  could be quite slow.
- The sequential IDs of boxes, posts, and delivered posts across
  different databases may conflict. A cheap solution is just to
  reset their sequences to start at very different values, and
  hope their ID ranges never intersect! A better solution would be
  to use UUIDs instead.

_IMAP access:_ Adding IMAP support would make our mail system just
like any other mail system, and would ensure that our messages can be
managed with any number of mail clients, including probably the one
which the user already prefers! A proliferation of mail clients and
systems can be a turn-off to users. The disadvantage is, the models
and API would probably need to be overhauled with IMAP compatibility
in mind. OTOH, if you go this route, an off-the-shelf IMAP server
might be more appropriate.

_Delivery agents:_ The proof of concept defers the processing of
subscriptions, but currently the mechanism that processes
subscriptions is only triggered when mail is retrieved. Background
processes could constantly work on bringing subscriptions
up-to-date. This would tradeoff speed of front-end retrieval
vs. resources consumed for inactive user accounts.

_Exception queue and retries:_ Currently, our deliver and sync actions
are not resilient to errors, refusing to process the rest of the box
if we encounter a database error during delivery. For this, and for
other cases where we might want to continue wth processing if we
encounter a sporadic error, we could implement an exception queue of
deliveries to retry later. For this queue I would recommend a fixed
number of retries, scheduled with a nonlinear backoff time interval.

_Deferring delivery:_ Mail systems like qmail queue up all delivery
requests to be processed in the background by a set of queue
processors. Once horizontal scaling comes into effect, and the
possibility of occasional failures in delivery becomes more plausible,
this deferral becomes much more attractive, even for simple mail
delivery tasks. This could be pursued as a complementary solution with
the exception queue. The disadvantage to deferred delivery is that the
user no longer knows if or when their message is actually available to
the recipients--receipts could be used to solve this problem.

_API schemas and documentation:_ For the back-end web service to be
a real platform, its API needs considerably more documentation than
what is currently presented.

## What I would do differently today

When this project was initially coded up, most of my web development
had been done in C++ on a proprietary and cobbled-together web stack. I
was well-versed with Python and Ruby, having used them for various
scripting projects, but had limited web development experience in them.

Since this initial assignment, I now have several years of Python web
development under my belt in Google App Engine, Pyramid, and Flask.
Front ends have been almost completely Javascript, eliminating a key
benefit of picking Django. So if I were coding this assignment today,
I would probably use Flask, but I also have my eye on Falcon
and Fast API and might have tried one of them on a lark.

I still love Python for web development, but recognize its performance
limitations more now than I did back then, particularly when rendering
large amounts of JSON. ASGI solves some of this, but Go was what I
transitioned to for a step up in performance, at the cost of losing much
of Python's concision.

When I first wrote the proof of concept, Docker was brand new to me,
and I had basically no experience with cloud providers. (That's
certainly changed over the years since then!) For getting this thing up
quickly and cheaply, I picked Heroku for deployment. I still like the
simplicity of platform-as-a-service solutions for application
deployment.
