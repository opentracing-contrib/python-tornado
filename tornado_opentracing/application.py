import opentracing

from .tracer import TornadoTracer


def tracer_config(__init__, app, args, kwargs):
    """
    Wraps the Tornado web application initialization so that the
    TornadoTracer instance is created around an OpenTracing-compatible tracer.
    """
    __init__(*args, **kwargs)

    tracer = app.settings.get('opentracing_tracer')

    if 'opentracing_trace_all' in app.settings:
        tracer._trace_all = app.settings['opentracing_trace_all']

    if 'opentracing_start_span_cb' in app.settings:
        tracer._start_span_cb = app.settings['opentracing_start_span_cb']
