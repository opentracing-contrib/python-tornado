import unittest

import tornado
import tornado_opentracing

from .dummies import DummyTracer

class TestApi(unittest.TestCase):
    def setUp(self):
        super(TestApi, self).setUp()

    def tearDown(self):
        super(TestApi, self).tearDown()
        tornado_opentracing._unpatch_tornado()
        tornado_opentracing._unpatch_tornado_client()

    def test_patch(self):
        tornado_opentracing.init_tracing()
        self.assertTrue(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))

    def test_client_patch(self):
        tracer = DummyTracer()
        tornado_opentracing.init_client_tracing(tracer)
        self.assertFalse(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))
        self.assertEqual(tornado_opentracing.httpclient.g_client_tracer, tracer)

    def test_client_subtracer(self):
        tracer = DummyTracer(with_subtracer=True)
        tornado_opentracing.init_client_tracing(tracer)
        self.assertFalse(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))
        self.assertEqual(tornado_opentracing.httpclient.g_client_tracer, tracer._tracer)

    def test_client_start_span(self):
        def test_cb(span, request):
            pass

        tornado_opentracing.init_client_tracing(DummyTracer(), start_span_cb=test_cb)
        self.assertEqual(tornado_opentracing.httpclient.g_start_span_cb, test_cb)

    def test_client_tracer_none(self):
        with self.assertRaises(ValueError):
            tornado_opentracing.init_client_tracing(None)

    def test_client_start_span_cb_invalid(self):
        with self.assertRaises(ValueError):
            tornado_opentracing.init_client_tracing(DummyTracer(),
                                                    start_span_cb=object())
