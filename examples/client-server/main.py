from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado import gen

import opentracing
import tornado_opentracing


def client_start_span_cb(span, request):
    span.operation_name = 'client/%s' % request.method
    span.set_tag('headers', request.headers)


# Pass your OpenTracing-compatible tracer here.
tracer = tornado_opentracing.TornadoTracer(opentracing.tracer)

# Since we are not using the global patching, we need to
# manually initialize the client.
tornado_opentracing.init_client_tracing(tracer, start_span_cb=client_start_span_cb)


class ClientLogHandler(RequestHandler):
    @tracer.trace()
    @gen.coroutine
    def get(self):
        yield AsyncHTTPClient().fetch('http://127.0.0.1:8080/server/log')
        self.write({'message': 'Sent a request to log'})


class ClientChildSpanHandler(RequestHandler):
    @tracer.trace()
    @gen.coroutine
    def get(self):
        yield AsyncHTTPClient().fetch('http://127.0.0.1:8080/server/childspan')
        self.write({'message': 'Sent a request that should procude an additional child span'})


class ServerLogHandler(RequestHandler):
    @tracer.trace()
    def get(self):
        span = tracer.get_span(self.request)
        span.log_event('Hello, world!')
        self.write({})


class ServerChildSpanHandler(RequestHandler):
    @tracer.trace()
    def get(self):
        span = tracer.get_span(self.request)
        with tracer._tracer.start_span('child_span', child_of=span.context):
            self.write({})


if __name__ == '__main__':
    app = Application([
            (r'/client/log', ClientLogHandler),
            (r'/client/childspan', ClientChildSpanHandler),
            (r'/server/log', ServerLogHandler),
            (r'/server/childspan', ServerChildSpanHandler),
        ],
        opentracing_tracer=tornado_opentracing.TornadoTracer(tracer),
        opentracing_trace_all=True,
        opentracing_trace_client=True,
    )
    app.listen(8080)
    IOLoop.current().start()
