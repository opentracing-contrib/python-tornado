import unittest

import tornado
import tornado_opentracing

class TestApi(unittest.TestCase):
    def setUp(self):
        super(TestApi, self).setUp()

    def tearDown(self):
        super(TestApi, self).tearDown()
        tornado_opentracing._unpatch_tornado()

    def test_patch(self):
        tornado_opentracing.init_tracing()
        self.assertTrue(getattr(tornado, '__opentracing_patch', False))
