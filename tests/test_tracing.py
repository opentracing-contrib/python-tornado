import unittest

from opentracing.mocktracer import MockTracer
from opentracing.scope_managers.tornado import TornadoScopeManager
import tornado.gen
import tornado.web
import tornado.testing
import tornado_opentracing


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('{}')


class ErrorHandler(tornado.web.RequestHandler):
    def get(self):
        raise ValueError('invalid input')


class ScopeHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def do_something(self):
        tracing = self.settings.get('opentracing_tracing')
        with tracing._tracer.start_active_span('Child'):
            tracing._tracer.active_span.set_tag('start', 0)
            yield tornado.gen.sleep(0.0)
            tracing._tracer.active_span.set_tag('end', 1)

    @tornado.gen.coroutine
    def get(self):
        tracing = self.settings.get('opentracing_tracing')
        span = tracing.get_span(self.request)
        assert span is not None
        assert tracing._tracer.active_span is span

        yield self.do_something()

        assert tracing._tracer.active_span is span
        self.write('{}')


def make_app(tracer, trace_all=None, trace_client=None,
             traced_attributes=None,start_span_cb=None):

    settings = {
        'opentracing_tracing': tornado_opentracing.TornadoTracing(tracer)
    }
    if trace_all is not None:
        settings['opentracing_trace_all'] = trace_all
    if trace_client is not None:
        settings['opentracing_trace_client'] = trace_client
    if traced_attributes is not None:
        settings['opentracing_traced_attributes'] = traced_attributes
    if start_span_cb is not None:
        settings['opentracing_start_span_cb'] = start_span_cb

    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/error', ErrorHandler),
            ('/coroutine_scope', ScopeHandler),
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
        tornado_opentracing._unpatch_tornado_client()
        super(TestTracing, self).tearDown()

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer, trace_all=True)

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'MainHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_error(self):
        response = self.fetch('/error')
        self.assertEqual(response.code, 500)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'ErrorHandler')

        tags = spans[0].tags
        self.assertEqual(tags.get('error', None), 'true')
        self.assertTrue(isinstance(tags.get('error.object', None), ValueError))

    def test_scope(self):
        response = self.fetch('/coroutine_scope')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 2)

        child = spans[0]
        self.assertTrue(child.finished)
        self.assertEqual(child.operation_name, 'Child')
        self.assertEqual(child.tags, {
            'start': 0,
            'end': 1,
        })

        parent = spans[1]
        self.assertTrue(parent.finished)
        self.assertEqual(parent.operation_name, 'ScopeHandler')
        self.assertEqual(parent.tags, {
            'component': 'tornado',
            'http.url': '/coroutine_scope',
            'http.method': 'GET',
            'http.status_code': 200,
        })

        # Same trace.
        self.assertEqual(child.context.trace_id, parent.context.trace_id)
        self.assertEqual(child.parent_id, parent.context.span_id)


class TestNoTraceAll(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestNoTraceAll, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        tornado_opentracing._unpatch_tornado_client()
        super(TestNoTraceAll, self).tearDown()

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer, trace_all=False)

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 0)


class TestTracedAttributes(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestTracedAttributes, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        tornado_opentracing._unpatch_tornado_client()
        super(TestTracedAttributes, self).tearDown()

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
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

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'MainHandler')
        self.assertEqual(spans[0].tags, {
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
        tornado_opentracing._unpatch_tornado_client()
        super(TestStartSpanCallback, self).tearDown()

    def start_span_cb(self, span, request):
        span.operation_name = 'foo/%s' % request.method
        span.set_tag('component', 'not-tornado')
        span.set_tag('custom-tag', 'custom-value')

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_all=True,
                        start_span_cb=self.start_span_cb)

    def test_start_span_cb(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'foo/GET')
        self.assertEqual(spans[0].tags, {
            'component': 'not-tornado',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
            'custom-tag': 'custom-value',
        })


class TestClient(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestClient, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        tornado_opentracing._unpatch_tornado_client()
        super(TestClient, self).tearDown()

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_all=False,
                        trace_client=True)

    def test_simple(self):
        response = self.fetch('/')
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


class TestClientCallback(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestClientCallback, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
        tornado_opentracing._unpatch_tornado_client()
        super(TestClientCallback, self).tearDown()

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_all=False,
                        trace_client=True,
                        start_span_cb=self.start_span_cb)

    def start_span_cb(self, span, request):
        span.operation_name = 'foo/%s' % request.method
        span.set_tag('component', 'not-tornado')
        span.set_tag('custom-tag', 'custom-value')

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'foo/GET')
        self.assertEqual(spans[0].tags, {
            'component': 'not-tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/'),
            'http.method': 'GET',
            'http.status_code': 200,
            'custom-tag': 'custom-value',
        })
