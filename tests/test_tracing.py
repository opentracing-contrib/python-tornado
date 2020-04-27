# Copyright The OpenTracing Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import mock
import unittest

import opentracing
from opentracing.mocktracer import MockTracer
import tornado.gen
import tornado.web
import tornado.testing
import tornado_opentracing
from tornado import version_info as tornado_version
from tornado_opentracing import TornadoTracing
from tornado_opentracing.scope_managers import TornadoScopeManager
from tornado_opentracing.context_managers import tornado_context

from .helpers import AsyncHTTPTestCase
from .helpers.handlers import AsyncScopeHandler
from .helpers.markers import (
    skip_generator_contextvars_on_tornado6,
    skip_no_async_await,
)


async_await_not_supported = (
    sys.version_info < (3, 5) or tornado_version < (5, 0)
)


class MainHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = (
        tornado.web.RequestHandler.SUPPORTED_METHODS + ('CUSTOM_METHOD',)
    )

    def get(self):
        self.write('{}')

    def custom_method(self):
        self.write('{}')


class ErrorHandler(tornado.web.RequestHandler):
    def get(self):
        raise ValueError('invalid input')


class CoroutineScopeHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def do_something(self):
        tracing = self.settings.get('opentracing_tracing')
        with tracing.tracer.start_active_span('Child'):
            tracing.tracer.active_span.set_tag('start', 0)
            yield tornado.gen.sleep(0.0)
            tracing.tracer.active_span.set_tag('end', 1)

    @tornado.gen.coroutine
    def get(self):
        tracing = self.settings.get('opentracing_tracing')
        span = tracing.get_span(self.request)
        assert span is not None
        assert tracing.tracer.active_span is span

        yield self.do_something()

        assert tracing.tracer.active_span is span
        self.write('{}')


def make_app(tracer=None, tracer_callable=None, tracer_parameters={},
             trace_all=None, trace_client=None,
             traced_attributes=None, start_span_cb=None):

    settings = {
    }
    if tracer is not None:
        settings['opentracing_tracing'] = TornadoTracing(tracer)
    if tracer_callable is not None:
        settings['opentracing_tracer_callable'] = tracer_callable
        settings['opentracing_tracer_parameters'] = tracer_parameters
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
            ('/coroutine_scope', CoroutineScopeHandler),
            ('/async_scope', AsyncScopeHandler),
        ],
        **settings
    )
    return app


class TestTornadoTracingValues(unittest.TestCase):
    def test_tracer(self):
        tracer = MockTracer()
        tracing = tornado_opentracing.TornadoTracing(tracer)
        self.assertEqual(tracing.tracer, tracer)

    @mock.patch('opentracing.tracer')
    def test_tracer_none(self, tracer):
        tracing = tornado_opentracing.TornadoTracing()
        self.assertEqual(tracing.tracer, opentracing.tracer)

        opentracing.tracer = mock.MagicMock()
        self.assertEqual(tracing.tracer, opentracing.tracer)

    def test_start_span_cb_invalid(self):
        with self.assertRaises(ValueError):
            tornado_opentracing.TornadoTracing(start_span_cb=[])


class TestTornadoTracingBase(AsyncHTTPTestCase):
    def setUp(self):
        tornado_opentracing.init_tracing()
        super(TestTornadoTracingBase, self).setUp()

    def tearDown(self):
        tornado_opentracing.initialization._unpatch_tornado()
        tornado_opentracing.initialization._unpatch_tornado_client()
        super(TestTornadoTracingBase, self).tearDown()


class TestInitWithoutTracingObj(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(start_span_cb=self.start_span_cb)

    def start_span_cb(self, span, request):
        span.set_tag('done', True)

    def test_default(self):
        # no-op opentracing.tracer should work silently.
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

    def test_case(self):
        with mock.patch('opentracing.tracer', new=self.tracer):
            response = self.fetch('/')
            self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 2)

        self.assertEqual(spans[0].operation_name, 'MainHandler')  # server
        self.assertEqual(spans[0].tags.get('done', None), True)

        self.assertEqual(spans[1].operation_name, 'GET')  # client
        self.assertEqual(spans[1].tags.get('done', None), True)


# dummy tracer callable for testing.
def tracer_callable(tracer):
    return tracer


class TestInitWithTracerCallable(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(tracer_callable=tracer_callable, tracer_parameters={
            'tracer': self.tracer,
        })

    def test_case(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 2)

        self.assertEqual(spans[0].operation_name, 'MainHandler')  # server
        self.assertEqual(spans[1].operation_name, 'GET')  # client


class TestInitWithTracerCallableStr(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(tracer_callable='tests.test_tracing.tracer_callable',
                        tracer_parameters={
                            'tracer': self.tracer
                        })

    def test_case(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 2)

        self.assertEqual(spans[0].operation_name, 'MainHandler')  # server
        self.assertEqual(spans[1].operation_name, 'GET')  # client


class TestTracing(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer, trace_client=False)

    def test_simple(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'MainHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
        })

    def test_custom_method(self):
        response = self.fetch(
            '/',
            method='CUSTOM_METHOD',
            allow_nonstandard_methods=True
        )
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'MainHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/',
            'http.method': 'CUSTOM_METHOD',
            'http.status_code': 200,
        })

    def test_error(self):
        response = self.http_fetch(self.get_url('/error'))
        self.assertEqual(response.code, 500)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'ErrorHandler')

        tags = spans[0].tags
        self.assertEqual(tags.get('error', None), True)
        self.assertEqual(tags.get('sfx.error.kind', None), 'ValueError')
        self.assertEqual(tags.get('sfx.error.object', None), '<class \'ValueError\'>')
        self.assertEqual(tags.get('sfx.error.message', None), 'invalid input')

    @skip_generator_contextvars_on_tornado6
    def test_scope_coroutine(self):
        response = self.http_fetch(self.get_url('/coroutine_scope'))
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
        self.assertEqual(parent.operation_name, 'CoroutineScopeHandler')
        self.assertEqual(parent.tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/coroutine_scope',
            'http.method': 'GET',
            'http.status_code': 200,
        })

        # Same trace.
        self.assertEqual(child.context.trace_id, parent.context.trace_id)
        self.assertEqual(child.parent_id, parent.context.span_id)

    @skip_no_async_await
    def test_scope_async(self):
        response = self.http_fetch(self.get_url('/async_scope'))
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
        self.assertEqual(parent.operation_name, 'AsyncScopeHandler')
        self.assertEqual(parent.tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/async_scope',
            'http.method': 'GET',
            'http.status_code': 200,
        })

        # Same trace.
        self.assertEqual(child.context.trace_id, parent.context.trace_id)
        self.assertEqual(child.parent_id, parent.context.span_id)


class TestNoTraceAll(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer, trace_all=False, trace_client=False)

    def test_simple(self):
        response = self.http_fetch(self.get_url('/'))
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 0)


class TestTracedAttributes(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_client=False,
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
            'span.kind': 'server',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
            'version': 'HTTP/1.1',
            'protocol': 'http',
        })


class TestStartSpanCallback(TestTornadoTracingBase):
    def start_span_cb(self, span, request):
        span.operation_name = 'foo/%s' % request.method
        span.set_tag('component', 'not-tornado')
        span.set_tag('custom-tag', 'custom-value')

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_client=False,
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
            'span.kind': 'server',
            'http.url': '/',
            'http.method': 'GET',
            'http.status_code': 200,
            'custom-tag': 'custom-value',
        })


class TestStartSpanCallbackException(TestTornadoTracingBase):
    def start_span_cb(self, span, request):
        raise RuntimeError('This should not happen')

    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_client=False,
                        start_span_cb=self.start_span_cb)

    def test_start_span_cb(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertFalse(spans[0].tags.get('error', False))


class TestClient(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_all=False)

    def test_simple(self):
        with tornado_context():
            response = self.http_fetch(self.get_url('/'), self.stop)

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


class TestClientCallback(TestTornadoTracingBase):
    def get_app(self):
        self.tracer = MockTracer(TornadoScopeManager())
        return make_app(self.tracer,
                        trace_all=False,
                        start_span_cb=self.start_span_cb)

    def start_span_cb(self, span, request):
        span.operation_name = 'foo/%s' % request.method
        span.set_tag('component', 'not-tornado')
        span.set_tag('custom-tag', 'custom-value')

    def test_simple(self):
        with tornado_context():
            response = self.http_fetch(self.get_url('/'), self.stop)

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
