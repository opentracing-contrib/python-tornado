import sys

import tornado_opentracing
from opentracing.mocktracer import MockTracer
from tornado_opentracing.scope_managers import ScopeManager


if sys.version_info >= (3, 3):
    from ._test_case_gen import AsyncHTTPTestCase  # noqa
else:
    from ._test_case import AsyncHTTPTestCase  # noqa


tracing = tornado_opentracing.TornadoTracing(MockTracer(ScopeManager()))
