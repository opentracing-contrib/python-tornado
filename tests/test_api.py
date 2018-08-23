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
import unittest

import opentracing
from opentracing.mocktracer import MockTracer
import tornado
import tornado_opentracing


class DummyTracer(object):
    def __init__(self, tracer):
        self._tracer = tracer


class TestApi(unittest.TestCase):
    def setUp(self):
        super(TestApi, self).setUp()

    def tearDown(self):
        super(TestApi, self).tearDown()
        tornado_opentracing.initialization._unpatch_tornado()
        tornado_opentracing.initialization._unpatch_tornado_client()

    def test_patch(self):
        tornado_opentracing.init_tracing()
        self.assertTrue(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))

    def test_client_patch(self):
        tracer = MockTracer()
        tornado_opentracing.init_client_tracing(tracer)
        self.assertFalse(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))
        self.assertEqual(tornado_opentracing.httpclient.g_client_tracer,
                         tracer)

    def test_client_subtracer(self):
        tracer = DummyTracer(MockTracer())
        tornado_opentracing.init_client_tracing(tracer)
        self.assertFalse(getattr(tornado, '__opentracing_patch', False))
        self.assertTrue(getattr(tornado, '__opentracing_client_patch', False))
        self.assertEqual(tornado_opentracing.httpclient.g_client_tracer,
                         tracer._tracer)

    def test_client_start_span(self):
        def test_cb(span, request):
            pass

        tornado_opentracing.init_client_tracing(
            MockTracer(),
            start_span_cb=test_cb
        )
        self.assertEqual(
            tornado_opentracing.httpclient.g_start_span_cb,
            test_cb
        )

    @mock.patch('opentracing.tracer')
    def test_client_tracer_none(self, tracer):
        tornado_opentracing.init_client_tracing()
        self.assertEqual(tornado_opentracing.httpclient._get_tracer(),
                         opentracing.tracer)

        opentracing.tracer = mock.MagicMock()
        self.assertEqual(tornado_opentracing.httpclient._get_tracer(),
                         opentracing.tracer)

    def test_client_start_span_cb_invalid(self):
        with self.assertRaises(ValueError):
            tornado_opentracing.init_client_tracing(MockTracer(),
                                                    start_span_cb=object())
