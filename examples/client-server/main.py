from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado import gen

import opentracing
from opentracing.scope_managers.tornado import TornadoScopeManager
import tornado_opentracing


def client_start_span_cb(span, request):
    span.operation_name = 'client/%s' % request.method
    span.set_tag('headers', request.headers)


# Pass your OpenTracing-compatible tracer here
# using TornadoScopeManager.
tracing = tornado_opentracing.TornadoTracing(opentracing.tracer)

# Since we are not doing a full tornado_opentracing.init_tracing(),
# we need to manually call init_client_tracing() if we want to do
# HTTP client tracing too.
tornado_opentracing.init_client_tracing(
    opentracing.tracer,
    start_span_cb=client_start_span_cb
)


class ClientLogHandler(RequestHandler):
    @tracing.trace()
    @gen.coroutine
    def get(self):
        yield AsyncHTTPClient().fetch('http://127.0.0.1:8080/server/log')
        self.write({'message': 'Sent a request to log'})


class ClientChildSpanHandler(RequestHandler):
    @tracing.trace()
    @gen.coroutine
    def get(self):
        yield AsyncHTTPClient().fetch('http://127.0.0.1:8080/server/childspan')
        self.write({
            'message': 'Sent a request that should procude an additional child span'
        })


class ServerLogHandler(RequestHandler):
    @tracing.trace()
    def get(self):
        # Alternatively, TornadoTracing.get_span(self.request)
        # can be used to fetch this request's Span.
        tracing.tracer.active_span.log_event('Hello, world!')
        self.write({})


class ServerChildSpanHandler(RequestHandler):
    @tracing.trace()
    def get(self):
        # Will implicitly be child of the incoming request Span.
        with tracing.tracer.start_active_span('extra_child_span'):
            self.write({})


if __name__ == '__main__':
    app = Application([
            (r'/client/log', ClientLogHandler),
            (r'/client/childspan', ClientChildSpanHandler),
            (r'/server/log', ServerLogHandler),
            (r'/server/childspan', ServerChildSpanHandler),
        ],
    )
    app.listen(8080)
    IOLoop.current().start()
