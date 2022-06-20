from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

import postweb.utils

register = template.Library()

@register.simple_tag
def service_url(service, *args, **kwargs):
    # extract path if it was given, default is empty string
    if len(args):
        path = args[0]
    elif 'path' in kwargs:
        path = kwargs['path']
    else:
        path = ''

    # template tags should fail gracefully
    try:
        return postweb.utils.service_url(service, path)
    except ValueError:
        return ''

@register.filter
@stringfilter
def represent_date(iso_datetime_str):
    return postweb.utils.represent_date(iso_datetime_str)

@register.filter
@stringfilter
def markdown_to_safe_html(markdown_text):
    return mark_safe(postweb.utils.markdown_to_html(markdown_text))
