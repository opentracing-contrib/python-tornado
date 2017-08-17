import tornado

from wrapt import wrap_function_wrapper as wrap_function, ObjectProxy

from . import application, handlers, httpclient
from .tracer import TornadoTracer


def init_tracing():
    _patch_tornado()
    _patch_tornado_client()


def init_client_tracing(tracer, start_span_cb=None):
    if tracer is None:
        raise ValueError('tracer')

    if hasattr(tracer, '_tracer'):
        tracer = tracer._tracer

    if start_span_cb is not None and not callable(start_span_cb):
        raise ValueError('start_span_cb')

    _patch_tornado_client(tracer, start_span_cb)


def _patch_tornado():
    # patch only once
    if getattr(tornado, '__opentracing_patch', False) is True:
        return

    setattr(tornado, '__opentracing_patch', True)

    wrap_function('tornado.web', 'Application.__init__', application.tracer_config)

    wrap_function('tornado.web', 'RequestHandler._execute', handlers.execute)
    wrap_function('tornado.web', 'RequestHandler.on_finish', handlers.on_finish)
    wrap_function('tornado.web', 'RequestHandler.log_exception', handlers.log_exception)


def _patch_tornado_client(tracer=None, start_span_cb=None):
    if getattr(tornado, '__opentracing_client_patch', False) is True:
        return

    setattr(tornado, '__opentracing_client_patch', True)
    httpclient._set_tracing_enabled(True)
    httpclient._set_tracing_info(tracer, start_span_cb)

    wrap_function('tornado.httpclient', 'AsyncHTTPClient.fetch', httpclient.fetch_async)


def _unpatch(obj, attr):
    f = getattr(obj, attr, None)
    if f and isinstance(f, ObjectProxy) and hasattr(f, '__wrapped__'):
        setattr(obj, attr, f.__wrapped__)


def _unpatch_tornado():
    if getattr(tornado, '__opentracing_patch', False) is False:
        return

    setattr(tornado, '__opentracing_patch', False)

    _unpatch(tornado.web.Application, '__init__')

    _unpatch(tornado.web.RequestHandler, '_execute')
    _unpatch(tornado.web.RequestHandler, 'on_finish')
    _unpatch(tornado.web.RequestHandler, 'log_exception')


def _unpatch_tornado_client():
    if getattr(tornado, '__opentracing_client_patch', False) is False:
        return

    setattr(tornado, '__opentracing_client_patch', False)

    _unpatch(tornado.httpclient.AsyncHTTPClient, 'fetch')
