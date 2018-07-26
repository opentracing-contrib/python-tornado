from tornado.web import HTTPError

from opentracing.scope_managers.tornado import tracer_stack_context


def execute(func, handler, args, kwargs):
    """
    Wrap the handler ``_execute`` method to trace incoming requests,
    extracting the context from the headers, if available.
    """
    tracing = handler.settings.get('opentracing_tracing')
    if tracing is None:
        return func(*args, **kwargs)

    with tracer_stack_context():
        if tracing._trace_all:
            attrs = handler.settings.get('opentracing_traced_attributes', [])
            tracing._apply_tracing(handler, attrs)

        return func(*args, **kwargs)


def on_finish(func, handler, args, kwargs):
    """
    Wrap the handler ``on_finish`` method to finish the Span for the
    given request, if available.
    """
    tracing = handler.settings.get('opentracing_tracing')
    if tracing is not None:
        tracing._finish_tracing(handler)

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

    tracing = handler.settings.get('opentracing_tracing')
    if tracing is not None:
        if not isinstance(value, HTTPError) or 500 <= value.status_code <= 599:
            tracing._finish_tracing(handler, error=value)

    return func(*args, **kwargs)
