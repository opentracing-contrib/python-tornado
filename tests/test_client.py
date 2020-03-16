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

import mock

from opentracing.mocktracer import MockTracer
import tornado.gen
from tornado.httpclient import HTTPRequest
import tornado.web
import tornado.testing
import tornado_opentracing
from tornado_opentracing.scope_managers import TornadoScopeManager
from tornado_opentracing.context_managers import tornado_context

from .helpers import AsyncHTTPTestCase


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


class TestClient(AsyncHTTPTestCase):
    def setUp(self):
        self.tracer = MockTracer(TornadoScopeManager())
        super(TestClient, self).setUp()

    def tearDown(self):
        tornado_opentracing.initialization._unpatch_tornado_client()
        super(TestClient, self).tearDown()

    def get_app(self):
        return make_app()

    def test_no_tracer(self):
        tornado_opentracing.init_client_tracing()

        with mock.patch('opentracing.tracer', new=self.tracer):
            with tornado_context():
                response = self.http_fetch(self.get_url('/'))

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

    def test_simple(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tornado_context():
            response = self.http_fetch(self.get_url('/'))

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

        with tornado_context():
            response = self.http_fetch(self.get_url('/'))

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

    def test_start_span_cb_exception(self):
        def test_cb(span, request):
            raise RuntimeError('This should not happen')

        tornado_opentracing.init_client_tracing(self.tracer,
                                                start_span_cb=test_cb)

        with tornado_context():
            response = self.http_fetch(self.get_url('/'))

        self.assertEqual(response.code, 200)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertFalse(spans[0].tags.get('error', False))

    def test_explicit_parameters(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tornado_context():
            response = self.http_fetch(
                self.get_url('/error'),
                raise_error=False,
                method='POST',
                body='')

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

        with tornado_context():
            response = self.http_fetch(HTTPRequest(self.get_url('/')))

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

        with tornado_context():
            response = self.http_fetch(self.get_url('/error'))

        self.assertEqual(response.code, 500)
        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertTrue(spans[0].finished)
        self.assertEqual(spans[0].operation_name, 'GET')

        tags = spans[0].tags
        self.assertEqual(tags.get('http.status_code', None), 500)
        self.assertEqual(tags.get('error', None), True)

        logs = spans[0].logs
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].key_values.get('event', None),
                         'error')
        self.assertTrue(isinstance(
            logs[0].key_values.get('error.object', None), Exception
        ))

    def test_server_not_found(self):
        tornado_opentracing.init_client_tracing(self.tracer)

        with tornado_context():
            response = self.http_fetch(
                self.get_url('/doesnotexist'),
                raise_error=False
            )

        self.assertEqual(response.code, 404)

        spans = self.tracer.finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].operation_name, 'GET')

        tags = spans[0].tags
        self.assertEqual(tags.get('http.status_code', None), 404)
        self.assertEqual(tags.get('error', None), None)  # no error.

        self.assertEqual(len(spans[0].logs), 0)
