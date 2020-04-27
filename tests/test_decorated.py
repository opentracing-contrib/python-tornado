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

import tornado.gen
import tornado.web
import tornado.testing
import tornado_opentracing
from tornado_opentracing.context_managers import tornado_context

from .helpers import tracing
from .helpers import AsyncHTTPTestCase
from .helpers.handlers import (
    DecoratedAsyncHandler,
    DecoratedAsyncScopeHandler,
    DecoratedAsyncErrorHandler
)
from .helpers.markers import (
    skip_generator_contextvars_on_tornado6,
    skip_generator_contextvars_on_py34,
    skip_no_async_await,
)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        # Not being traced.
        assert tracing.get_span(self.request) is None
        self.write('{}')


class DecoratedHandler(tornado.web.RequestHandler):
    @tracing.trace('protocol', 'doesntexist')
    def get(self):
        assert tracing.get_span(self.request) is not None
        self.write('{}')


class DecoratedErrorHandler(tornado.web.RequestHandler):
    @tracing.trace()
    def get(self):
        assert tracing.get_span(self.request) is not None
        raise ValueError('invalid value')


class DecoratedCoroutineHandler(tornado.web.RequestHandler):
    @tracing.trace('protocol', 'doesntexist')
    @tornado.gen.coroutine
    def get(self):
        yield tornado.gen.sleep(0)
        self.set_status(201)
        self.write('{}')


class DecoratedCoroutineErrorHandler(tornado.web.RequestHandler):
    @tracing.trace()
    @tornado.gen.coroutine
    def get(self):
        yield tornado.gen.sleep(0)
        raise ValueError('invalid value')


class DecoratedCoroutineScopeHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def do_something(self):
        with tracing.tracer.start_active_span('Child'):
            tracing.tracer.active_span.set_tag('start', 0)
            yield tornado.gen.sleep(0)
            tracing.tracer.active_span.set_tag('end', 1)

    @tracing.trace()
    @tornado.gen.coroutine
    def get(self):
        span = tracing.get_span(self.request)
        assert span is not None
        assert tracing.tracer.active_span is span

        yield self.do_something()

        assert tracing.tracer.active_span is span
        self.set_status(201)
        self.write('{}')


def make_app(with_tracing_obj=False):
    settings = {}
    if with_tracing_obj:
        settings['opentracing_tracing'] = tracing
        settings['opentracing_trace_client'] = False

    app = tornado.web.Application(
        [
            ('/', MainHandler),
            ('/decorated', DecoratedHandler),
            ('/decorated_error', DecoratedErrorHandler),
            ('/decorated_coroutine', DecoratedCoroutineHandler),
            ('/decorated_coroutine_error', DecoratedCoroutineErrorHandler),
            ('/decorated_coroutine_scope', DecoratedCoroutineScopeHandler),
            ('/decorated_async', DecoratedAsyncHandler),
            ('/decorated_async_error', DecoratedAsyncErrorHandler),
            ('/decorated_async_scope', DecoratedAsyncScopeHandler),
        ],
        **settings
    )
    return app


class TestDecorated(tornado.testing.AsyncHTTPTestCase):
    def tearDown(self):
        tracing.tracer.reset()
        super(TestDecorated, self).tearDown()

    def get_app(self):
        return make_app()

    def test_no_traced(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 200)
        self.assertEqual(len(tracing.tracer.finished_spans()), 0)

    def test_simple(self):
        response = self.fetch('/decorated')
        self.assertEqual(response.code, 200)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'DecoratedHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated',
            'http.method': 'GET',
            'http.status_code': 200,
            'protocol': 'http',
        })

    def test_error(self):
        response = self.fetch('/decorated_error')
        self.assertEqual(response.code, 500)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'DecoratedErrorHandler')

        tags = spans[0].tags
        self.assertEqual(tags.get('error', None), True)
        self.assertEqual(tags.get('sfx.error.kind', None), 'ValueError')
        self.assertEqual(tags.get('sfx.error.object', None), '<class \'ValueError\'>')
        self.assertEqual(tags.get('sfx.error.message', None), 'invalid value')

    @skip_generator_contextvars_on_tornado6
    @skip_generator_contextvars_on_py34
    def test_coroutine(self):
        response = self.fetch('/decorated_coroutine')
        self.assertEqual(response.code, 201)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'DecoratedCoroutineHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated_coroutine',
            'http.method': 'GET',
            'http.status_code': 201,
            'protocol': 'http',
        })

    @skip_generator_contextvars_on_tornado6
    @skip_generator_contextvars_on_py34
    def test_coroutine_error(self):
        response = self.fetch('/decorated_coroutine_error')
        self.assertEqual(response.code, 500)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name,
                         'DecoratedCoroutineErrorHandler')

        tags = spans[0].tags

        logs = spans[0].logs
        #self.assertEqual(len(logs), 1)
        #self.assertEqual(logs[0].key_values.get('event', None),
        #                 'error')
        #self.assertTrue(isinstance(
        #    logs[0].key_values.get('error.object', None), ValueError
        #))

        self.assertEqual(tags.get('error', None), True)
        self.assertEqual(tags.get('sfx.error.kind', None), 'ValueError')
        self.assertEqual(tags.get('sfx.error.object', None), '<class \'ValueError\'>')
        self.assertEqual(tags.get('sfx.error.message', None), 'invalid value')

    @skip_generator_contextvars_on_tornado6
    @skip_generator_contextvars_on_py34
    def test_coroutine_scope(self):
        response = self.fetch('/decorated_coroutine_scope')
        self.assertEqual(response.code, 201)

        spans = tracing.tracer.finished_spans()
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
        self.assertEqual(parent.operation_name,
                         'DecoratedCoroutineScopeHandler')
        self.assertEqual(parent.tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated_coroutine_scope',
            'http.method': 'GET',
            'http.status_code': 201,
        })

        # Same trace.
        self.assertEqual(child.context.trace_id, parent.context.trace_id)
        self.assertEqual(child.parent_id, parent.context.span_id)

    @skip_no_async_await
    def test_async(self):
        response = self.fetch('/decorated_async')
        self.assertEqual(response.code, 201)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'DecoratedAsyncHandler')
        self.assertEqual(spans[0].tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated_async',
            'http.method': 'GET',
            'http.status_code': 201,
            'protocol': 'http',
        })

    @skip_no_async_await
    def test_async_error(self):
        response = self.fetch('/decorated_async_error')
        self.assertEqual(response.code, 500)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name,
                         'DecoratedAsyncErrorHandler')

        tags = spans[0].tags
        self.assertEqual(tags.get('error', None), True)
        self.assertEqual(tags.get('sfx.error.kind', None), 'ValueError')
        self.assertEqual(tags.get('sfx.error.object', None), '<class \'ValueError\'>')
        self.assertEqual(tags.get('sfx.error.message', None), 'invalid value')

    @skip_no_async_await
    def test_async_scope(self):
        response = self.fetch('/decorated_async_scope')
        self.assertEqual(response.code, 201)

        spans = tracing.tracer.finished_spans()
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
        self.assertEqual(parent.operation_name,
                         'DecoratedAsyncScopeHandler')
        self.assertEqual(parent.tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated_async_scope',
            'http.method': 'GET',
            'http.status_code': 201,
        })

        # Same trace.
        self.assertEqual(child.context.trace_id, parent.context.trace_id)
        self.assertEqual(child.parent_id, parent.context.span_id)


class TestDecoratedAndTraceAll(tornado.testing.AsyncHTTPTestCase):
    def setUp(self):
        self._prev_trace_all = tracing._trace_all
        tornado_opentracing.init_tracing()
        super(TestDecoratedAndTraceAll, self).setUp()

    def tearDown(self):
        tracing.tracer.reset()
        tracing._trace_all = self._prev_trace_all
        tornado_opentracing.initialization._unpatch_tornado()
        tornado_opentracing.initialization._unpatch_tornado_client()
        super(TestDecoratedAndTraceAll, self).tearDown()

    def get_app(self):
        return make_app(with_tracing_obj=True)

    def test_only_one_span(self):
        # Even though trace_all=True and we are decorating
        # this handler, we should trace it only ONCE.
        response = self.fetch('/decorated')
        self.assertEqual(response.code, 200)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)


class TestClientIntegration(AsyncHTTPTestCase):
    def tearDown(self):
        tornado_opentracing.initialization._unpatch_tornado_client()
        tracing.tracer.reset()
        super(TestClientIntegration, self).tearDown()

    def get_app(self):
        return make_app()

    def test_simple(self):
        tornado_opentracing.init_client_tracing(tracing)

        with tornado_context():
            response = self.http_fetch(self.get_url('/decorated'))

        self.assertEqual(response.code, 200)

        spans = tracing.tracer.finished_spans()
        self.assertEqual(len(spans), 2)

        # Client
        span = spans[1]
        self.assertTrue(span.finished)
        self.assertEqual(span.operation_name, 'GET')
        self.assertEqual(span.tags, {
            'component': 'tornado',
            'span.kind': 'client',
            'http.url': self.get_url('/decorated'),
            'http.method': 'GET',
            'http.status_code': 200,
        })

        # Server
        span2 = spans[0]
        self.assertTrue(span2.finished)
        self.assertEqual(span2.operation_name, 'DecoratedHandler')
        self.assertEqual(span2.tags, {
            'component': 'tornado',
            'span.kind': 'server',
            'http.url': '/decorated',
            'http.method': 'GET',
            'http.status_code': 200,
            'protocol': 'http',
        })

        # Make sure the context was propagated,
        # and the client/server have the proper child_of relationship.
        self.assertEqual(span.context.trace_id, span2.context.trace_id)
        self.assertEqual(span.context.span_id, span2.parent_id)
