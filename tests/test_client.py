import unittest

from opentracing.mocktracer import MockTracer
from opentracing.scope_managers.tornado import TornadoScopeManager
from opentracing.scope_managers.tornado import tracer_stack_context
import tornado.gen
from tornado.httpclient import HTTPError, HTTPRequest
import tornado.web
import tornado.testing
import tornado_opentracing



class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('{}')


class ErrorHandler(tornado.web.RequestHandler):
    def get(self):
        raise ValueError('invalid input')

    def post(self):
        raise ValueError('invalid input')


def make_app():
    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/error', ErrorHandler),
        ]
    )
    return app


class TestClient(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        self.tracer = MockTracer(TornadoScopeManager())
        super(TestClient, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado_client()
        super(TestClient, self).tearDown()

    def get_app(self):
        return make_app()

    def test_simple(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tracer_stack_context():
            self.http_client.fetch(self.get_url('/'), self.stop)

        response = self.wait()
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'GET')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/'),
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_start_span_cb(self):
        def test_cb(span, request):
            span.operation_name = 'foo/' + request.method
            span.set_tag('component', 'tornado-client')

        tornado_opentracing.init_client_tracing(self.tracer,
                                                start_span_cb=test_cb)

        with tracer_stack_context():
            self.http_client.fetch(self.get_url('/'), self.stop)

        response = self.wait()
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'foo/GET')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado-client',
            'span.kind': 'client',
            'http.url': self.get_url('/'),
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_explicit_parameters(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tracer_stack_context():
            self.http_client.fetch(self.get_url('/error'),
                                   self.stop,
                                   raise_error=False,
                                   method='POST',
                                   body='')
        response = self.wait()
        self.assertEqual(response.code, 500)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'POST')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/error'),
            'http.method': 'POST',
            'http.status_code': 500,
        })

    def test_request_obj(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tracer_stack_context():
            self.http_client.fetch(HTTPRequest(self.get_url('/')), self.stop)

        response = self.wait()

        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'GET')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/'),
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_server_error(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tracer_stack_context():
            self.http_client.fetch(self.get_url('/error'), self.stop)

        response = self.wait()
        self.assertEqual(response.code, 500)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'GET')

        tags = spans[0].tags
        self.assertEqual(tags.get('http.status_code', None), 500)
