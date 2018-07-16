from tornado.web import HTTPError

import opentracing
from opentracing.scope_managers.tornado import tracer_stack_context


def execute(func, handler, args, kwargs):
    """
    Wrap the handler ``_execute`` method to trace incoming requests,
    extracting the context from the headers, if available.
    """
    tracer = handler.settings.get('opentracing_tracer', opentracing.tracer)

    span = None
    if tracer._trace_all:
        traced_attrs = handler.settings.get('opentracing_traced_attributes', [])
        span = tracer._apply_tracing(handler, traced_attrs)

    # TODO: if we trace_all=False, should we still do scope management?
    with tracer_stack_context():
        if span is not None:
            tracer._tracer.scope_manager.activate(span, False)

        return func(*args, **kwargs)


def on_finish(func, handler, args, kwargs):
    """
    Wrap the handler ``on_finish`` method to finish the Span for the
    given request, if available.
    """
    tracer = handler.settings.get('opentracing_tracer', opentracing.tracer)
    tracer._finish_tracing(handler)

    return func(*args, **kwargs)

def log_exception(func, handler, args, kwargs):
    """
    Wrap the handler ``log_exception`` method to finish the Span for the
    given request, if available. This method is called when an Exception
    is not handled in the user code.
    """
    # safe-guard: expected arguments -> log_exception(self, typ, value, tb)
    value = args[1] if len(args) == 3 else None
    if value is None:
        return func(*args, **kwargs)

    tracer = handler.settings.get('opentracing_tracer')
    if not isinstance(value, HTTPError) or 500 <= value.status_code <= 599:
        tracer._finish_tracing(handler, error=value)

    return func(*args, **kwargs)
