from django.conf import settings
import dateutil.parser

def service_url(service, path=''):
    '''Construct a URL for accessing the named service.'''
    if path.startswith('/'):
        path = path[1:]
    
    service_def = settings.SERVICES.get(service, None)
    if service_def is None:
        raise ValueError('No service named %s configured in settings.SERVICES' % service)

    endpoint = service_def.get('endpoint', None)
    if endpoint is None:
        raise ValueError('No endpoint configured in settings.SERVICES for %s' % service)

    if not endpoint.endswith('/'):
        endpoint = endpoint + '/'

    return endpoint + path

def represent_date(iso_datetime_str):
    '''Converts ISO-8601 datetime representation to something more readable.

    TODO: This should be internationalized.'''
    dt = dateutil.parser.parse(iso_datetime_str)
    return dt.strftime("%a %b %d %Y %I:%M %p")
