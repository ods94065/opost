import bleach
from django.conf import settings
import dateutil.parser
import markdown


markdown = markdown.Markdown()

# Tags suitable for rendering markdown
# From https://github.com/yourcelf/bleach-allowlist/blob/main/bleach_allowlist/bleach_allowlist.py
MARKDOWN_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "b",
    "i",
    "strong",
    "em",
    "tt",
    "p",
    "br",
    "span",
    "div",
    "blockquote",
    "code",
    "pre",
    "hr",
    "ul",
    "ol",
    "li",
    "dd",
    "dt",
    "img",
    "a",
    "sub",
    "sup",
]

MARKDOWN_ATTRS = {
    "*": ["id"],
    "img": ["src", "alt", "title"],
    "a": ["href", "alt", "title"],
}


def service_url(service, path=""):
    """Construct a URL for accessing the named service."""

    if path.startswith("/"):
        path = path[1:]

    service_def = settings.SERVICES.get(service, None)
    if service_def is None:
        raise ValueError(f"No service named {service} configured in settings.SERVICES")

    endpoint = service_def.get("endpoint", None)
    if endpoint is None:
        raise ValueError(f"No endpoint configured in settings.SERVICES for {service}")

    if not endpoint.endswith("/"):
        endpoint = endpoint + "/"

    return endpoint + path


def represent_date(iso_datetime_str):
    """Converts ISO-8601 datetime representation to something more readable.

    TODO: This should be internationalized.
    """

    dt = dateutil.parser.parse(iso_datetime_str)
    return dt.strftime("%a %b %d %Y %I:%M %p")


def markdown_to_html(markdown_text):
    """Converts Markdown to HTML.

    To avoid XSS vulnerabilities, only certain HTML tags will be allowed
    in the Markdown text.
    """

    return bleach.clean(
        markdown.convert(markdown_text),
        tags=MARKDOWN_TAGS,
        attributes=MARKDOWN_ATTRS,
    )
