import unittest

import tornado.gen
import tornado.web
import tornado.testing
import tornado_opentracing

from .dummies import DummyTracer


tracer = tornado_opentracing.TornadoTracer(DummyTracer())


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('{}')


class DecoratedHandler(tornado.web.RequestHandler):
    @tracer.trace('protocol', 'doesntexist')
    def get(self):
        self.write('{}')


class DecoratedErrorHandler(tornado.web.RequestHandler):
    @tracer.trace()
    def get(self):
        raise ValueError('invalid value')


class DecoratedCoroutineHandler(tornado.web.RequestHandler):
    @tracer.trace('protocol', 'doesntexist')
    @tornado.gen.coroutine
    def get(self):
        yield tornado.gen.sleep(0)
        self.set_status(201)
        self.write('{}')


class DecoratedCoroutineErrorHandler(tornado.web.RequestHandler):
    @tracer.trace()
    @tornado.gen.coroutine
    def get(self):
        yield tornado.gen.sleep(0)
        raise ValueError('invalid value')


def make_app():
    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/decorated', DecoratedHandler),
            ('/decorated_error', DecoratedErrorHandler),
            ('/decorated_coroutine', DecoratedCoroutineHandler),
            ('/decorated_coroutine_error', DecoratedCoroutineErrorHandler),
        ],
    )
    return app


class TestDecorated(tornado.testing.AsyncHTTPTestCase):
    def tearDown(self):
        tracer._tracer.clear()
        super(TestDecorated, self).tearDown()

    def get_app(self):
        return make_app()

    def test_no_traced(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(tracer._tracer.spans), 0)

    def test_simple(self):
        response = self.fetch('/decorated')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(tracer._tracer.spans), 1)
        self.assertTrue(tracer._tracer.spans[0].is_finished)
        self.assertEqual(tracer._tracer.spans[0].operation_name, 'DecoratedHandler')
        self.assertEqual(tracer._tracer.spans[0].tags, {
            'component': 'tornado',
            'http.url': '/decorated',
            'http.method': 'GET',
            'http.status_code': 200,
            'protocol': 'http',
        })

    def test_error(self):
        response = self.fetch('/decorated_error')
        self.assertEqual(response.code, 500)
        self.assertEqual(len(tracer._tracer.spans), 1)
        self.assertTrue(tracer._tracer.spans[0].is_finished)
        self.assertEqual(tracer._tracer.spans[0].operation_name, 'DecoratedErrorHandler')

        tags = tracer._tracer.spans[0].tags
        self.assertEqual(tags.get('error', None), 'true')
        self.assertTrue(isinstance(tags.get('error.object', None), ValueError))

    def test_coroutine(self):
        response = self.fetch('/decorated_coroutine')
        self.assertEqual(response.code, 201)
        self.assertEqual(len(tracer._tracer.spans), 1)
        self.assertTrue(tracer._tracer.spans[0].is_finished)
        self.assertEqual(tracer._tracer.spans[0].operation_name, 'DecoratedCoroutineHandler')
        self.assertEqual(tracer._tracer.spans[0].tags, {
            'component': 'tornado',
            'http.url': '/decorated_coroutine',
            'http.method': 'GET',
            'http.status_code': 201,
            'protocol': 'http',
        })

    def test_coroutine_error(self):
        response = self.fetch('/decorated_coroutine_error')
        self.assertEqual(response.code, 500)
        self.assertEqual(len(tracer._tracer.spans), 1)
        self.assertTrue(tracer._tracer.spans[0].is_finished)
        self.assertEqual(tracer._tracer.spans[0].operation_name, 'DecoratedCoroutineErrorHandler')

        tags = tracer._tracer.spans[0].tags
        self.assertEqual(tags.get('error', None), 'true')
        self.assertTrue(isinstance(tags.get('error.object', None), ValueError))


class TestClientIntegration(tornado.testing.AsyncHTTPTestCase):
    def tearDown(self):
        tornado_opentracing._unpatch_tornado_client()
        tracer._tracer.clear()
        super(TestClientIntegration, self).tearDown()

    def get_app(self):
        return make_app()

    def test_simple(self):
        tornado_opentracing.init_client_tracing(tracer)

        response = self.fetch('/decorated')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(tracer._tracer.spans), 2)

        # Client
        span = tracer._tracer.spans[0]
        self.assertTrue(span.is_finished)
        self.assertEqual(span.operation_name, 'GET')
        self.assertEqual(span.tags, {
            'component': 'tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/decorated'),
            'http.method': 'GET',
            'http.status_code': 200,
        })

        # Server
        span2 = tracer._tracer.spans[1]
        self.assertTrue(span2.is_finished)
        self.assertEqual(span2.operation_name, 'DecoratedHandler')
        self.assertEqual(span2.tags, {
            'component': 'tornado',
            'http.url': '/decorated',
            'http.method': 'GET',
            'http.status_code': 200,
            'protocol': 'http',
        })

        # Make sure the headers were injected/extracted,
        # from the client to the server.
        extracted_headers = tracer._tracer.extracted_headers
        self.assertEqual(len(extracted_headers), 1)
        self.assertEqual(extracted_headers[0].get('Ot-Format', None), 'http_headers')
        self.assertEqual(extracted_headers[0].get('Ot-Headers', None), 'true')
