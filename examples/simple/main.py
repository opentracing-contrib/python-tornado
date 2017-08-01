from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler

import opentracing
import tornado_opentracing


tornado_opentracing.init_tracing()

# Your OpenTracing-compatible tracer here.
tracer = opentracing.Tracer()

class MainHandler(RequestHandler):
    def get(self):
        self.write({'status': 'ok'})


class StoryHandler(RequestHandler):
    def get(self, story_id):
        if int(story_id) == 0:
            raise ValueError('invalid value passed')
        self.write({'status': 'fetched'})


app = Application([
        (r'/', MainHandler),
        (r'/story/([0-9]+)', StoryHandler),
    ],
    opentracing_tracer=tornado_opentracing.TornadoTracer(tracer),
    opentracing_trace_all=True,
    opentracing_traced_attributes=['protocol', 'method'],
)
app.listen(8080)
IOLoop.current().start()
