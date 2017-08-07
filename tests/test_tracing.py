import unittest

import tornado.gen
import tornado.web
import tornado.testing
import tornado_opentracing

from .dummies import DummyTracer


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('{}')


class ErrorHandler(tornado.web.RequestHandler):
    def get(self):
        raise ValueError('invalid input')


def make_app(tracer, trace_all=None, traced_attributes=None, start_span_cb=None):
    settings = {
        'opentracing_tracer': tornado_opentracing.TornadoTracer(tracer)
    }
    if trace_all is not None:
        settings['opentracing_trace_all'] = trace_all
    if traced_attributes is not None:
        settings['opentracing_traced_attributes'] = traced_attributes
    if start_span_cb is not None:
        settings['opentracing_start_span_cb'] = start_span_cb

    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/error', ErrorHandler),
        ],
        **settings
    )
    return app


class TestTracing(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestTracing, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        super(TestTracing, self).tearDown()

    def get_app(self):
        self.tracer = DummyTracer()
        return make_app(self.tracer, trace_all=True)

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(self.tracer.spans), 1)
        self.assertTrue(self.tracer.spans[0].is_finished)
        self.assertEqual(self.tracer.spans[0].operation_name, 'MainHandler')
        self.assertEqual(self.tracer.spans[0].tags, {
            'component': 'tornado',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_error(self):
        response = self.fetch('/error')
        self.assertEqual(response.code, 500)
        self.assertEqual(len(self.tracer.spans), 1)
        self.assertTrue(self.tracer.spans[0].is_finished)
        self.assertEqual(self.tracer.spans[0].operation_name, 'ErrorHandler')

        tags = self.tracer.spans[0].tags
        self.assertEqual(tags.get('error', None), 'true')
        self.assertTrue(isinstance(tags.get('error.object', None), ValueError))


class TestNoTraceAll(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestNoTraceAll, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        super(TestNoTraceAll, self).tearDown()

    def get_app(self):
        self.tracer = DummyTracer()
        return make_app(self.tracer, trace_all=False)

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(self.tracer.spans), 0)


class TestTracedAttributes(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestTracedAttributes, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        super(TestTracedAttributes, self).tearDown()

    def get_app(self):
        self.tracer = DummyTracer()
        return make_app(self.tracer,
                       trace_all=True,
                       traced_attributes=[
                           'version',
                           'protocol',
                           'doesnotexist',
                       ])

    def test_traced_attributes(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(self.tracer.spans), 1)
        self.assertTrue(self.tracer.spans[0].is_finished)
        self.assertEqual(self.tracer.spans[0].operation_name, 'MainHandler')
        self.assertEqual(self.tracer.spans[0].tags, {
            'component': 'tornado',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
            'version': 'HTTP/1.1',
            'protocol': 'http',
        })


class TestStartSpanCallback(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestStartSpanCallback, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        super(TestStartSpanCallback, self).tearDown()

    def start_span_cb(self, span, request):
        span.operation_name = 'foo/%s' % request.method
        span.set_tag('component', 'not-tornado')
        span.set_tag('custom-tag', 'custom-value')

    def get_app(self):
        self.tracer = DummyTracer()
        return make_app(self.tracer,
                        trace_all=True,
                        start_span_cb=self.start_span_cb)

    def test_start_span_cb(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(self.tracer.spans), 1)
        self.assertTrue(self.tracer.spans[0].is_finished)
        self.assertEqual(self.tracer.spans[0].operation_name, 'foo/GET')
        self.assertEqual(self.tracer.spans[0].tags, {
            'component': 'not-tornado',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
            'custom-tag': 'custom-value',
        })
