import opentracing

from .tracing import TornadoTracing
from . import httpclient


def tracer_config(__init__, app, args, kwargs):
    """
    Wraps the Tornado web application initialization so that the
    TornadoTracing instance is created around an OpenTracing-compatible tracer.
    """
    __init__(*args, **kwargs)

    tracing = app.settings.get('opentracing_tracing')

    if 'opentracing_trace_all' in app.settings:
        tracing._trace_all = app.settings['opentracing_trace_all']

    if 'opentracing_trace_client' in app.settings:
        tracing._trace_client = app.settings['opentracing_trace_client']

    if 'opentracing_start_span_cb' in app.settings:
        tracing._start_span_cb = app.settings['opentracing_start_span_cb']

    httpclient._set_tracing_enabled(tracing._trace_client)
    if tracing._trace_client:
        httpclient._set_tracing_info(tracing._tracer, tracing._start_span_cb)
