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
    @tornado.gen.coroutine
    def get(self):
        yield tornado.gen.sleep(0)
        self.write('{}')


def make_app():
    settings = {
        'opentracing_tracer': tracer,
        'opentracing_trace_all': False,
    }
    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/decorated', DecoratedHandler),
        ],
        **settings
    )
    return app


class TestDecorated(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestDecorated, self).setUp()

    def tearDown(self):
        tornado_opentracing._unpatch_tornado()
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
