from django.conf import settings
from django.core.urlresolvers import reverse
import json
import logging
import requests
from postweb.utils import service_url

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    pass

def dump_headers(headers):
    def dump_header(hdr):
        return ': '.join((hdr, headers[hdr]))
    return '\n'.join(dump_header(hdr) for hdr in sorted(headers.keys()))

class ServiceResponseError(ServiceError):
    def __init__(self, response):
        super(ServiceResponseError, self).__init__()
        self.response = response

    def __str__(self):
        return "Unknown response error, code %d\n%s" % (self.response.status_code, self.dump_response())

class ServiceResponseError(ServiceError):
    '''A general category of errors that have to do with the response we get back from a service.'''
    def __init__(self, response):
        super(ServiceResponseError, self).__init__()
        self.response = response

    def dump_response(self):
        return "%s\n\n%s" % (dump_headers(self.response.headers), self.response.text)

    def __str__(self):
        return "Service returned HTTP code %d:\n%s" % (self.response.status_code,
                                                       self.dump_response())

class ServiceResponseNotJsonError(ServiceResponseError):
    '''An error when the response we get back does not have JSON content and we are expecting some.'''
    def __init__(self, response):
        super(ServiceResponseNotJsonError, self).__init__(response)
        
    def __str__(self):
        return "Service response is not JSON (content type is %s):\n%s" % (self.response.headers['content-type'],
                                                                           self.dump_response())

class Service(object):
    def __init__(self, request):
        self.request = request
        self.config = settings.SERVICES['postapi']
        self.http = requests.Session()
        self.http.auth = (self.config['user'], self.config['password'])

    def response_to_json(self, response):
        '''Ensure the response is JSON, and return the parsed object.
        
        Raises ServiceResposeNotJsonError if the response has the wrong content type or cannot be parsed.'''
        # stip off any content type parameters if necessary
        content_type = response.headers['content-type'].partition(';')[0]

        # be sure to handle any JSON-based MIME media types, not just the generic application/json
        if content_type != 'application/json' and not content_type.endswith('+json'):
            raise ServiceResponseNotJsonError(response)

        try:
            return response.json()
        except ValueError:
            raise ServiceResponseNotJsonError(response)
        
class BoxService(Service):
    def get_box(self, name):
        '''Returns the box with the given name, or None if no such box can be found.

        Raises ServiceError if there was an issue with the service.'''
        logger.info("Fetching box for %s" % name)
        url = service_url('postapi', 'boxes/%s' % name)
        r = self.http.get(url, headers={'Accept': 'application/json'})
        if r.status_code == 404:
            return None
        elif not r.ok:
            raise ServiceResponseError(r)
        else:
            return self.response_to_json(r)

    def create_box(self, name):
        '''Creates a box with the given name.

        Raises ServiceError if there was an issue with the service.'''
        logger.info("Creating box for %s" % name)
        data = { 'name': name }
        url = service_url('boxes')
        r = self.http.post(url, data=json.dumps(data),
                           headers={'Content-Type': 'application/json',
                                    'Accept': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)
        
        return self.response_to_json(r)

    def sync(self, box_url):
        data = { 'box': box_url }
        logger.info("Syncing box %s" % box_url)
        url = service_url('postapi', 'actions/sync')
        r = self.http.post(url, data=json.dumps(data),
                           headers={'Content-Type': 'application/json',
                                    'Accept': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)

class PostService(Service):
    def get_delivered_post(self, dpost_url):
        logger.info("Getting post: %s" % dpost_url)
        r = self.http.get(dpost_url, headers={'Accept': 'application/json'})

        if not r.ok:
            raise ServiceResponseError(r)

        return self.response_to_json(r)

    def get_post_detail(self, dpost_pk):
        logger.info("Viewing post details with delivered post id: %s" % dpost_pk)
        url = service_url('postapi', 'delivered-posts/%s' % dpost_pk)
        r = self.http.get(url, headers={'Accept': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)
        dpost = self.response_to_json(r)
        logger.info("Fetching post body: %s" % dpost['post'])
        r = self.http.get(dpost['post'], headers={'Accept': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)
        dpost['post'] = self.response_to_json(r)
        return dpost

    def delete_post(self, dpost_pk):
        logger.info("Deleting delivered post id: %s" % dpost_pk)
        url = service_url('postapi', 'delivered-posts/%s' % dpost_pk)
        r = self.http.delete(url, headers={'Accept': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)

    def send_post(self, boxes, subject, body):
        logger.info("Sending message to:\n%s" % '\n'.join(boxes))
        url = service_url('postapi', 'actions/deliver')
        data = {'to': boxes, 'subject': subject, 'body': body}
        r = self.http.post(url, data=json.dumps(data),
                           headers={'Content-Type': 'application/json',
                                    'Accepts': 'application/json'})
        if not r.ok:
            raise ServiceResponseError(r)
        return self.response_to_json(r)
