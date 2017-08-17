import functools

import opentracing


class TornadoTracer(object):
    '''
    @param tracer the OpenTracing tracer to be used
    to trace requests using this TornadoTracer
    '''
    def __init__(self, tracer, trace_all=False, trace_client=False,
                 start_span_cb=None):
        self._tracer = tracer
        self._trace_all = trace_all
        self._trace_client = trace_client
        self._start_span_cb = start_span_cb
        self._current_spans = {}

    def get_span(self, request):
        '''
        @param request 
        Returns the span tracing this request
        '''
        return self._current_spans.get(request, None)

    def trace(self, *attributes):
        '''
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span
        '''
        def decorator(func):
            if self._trace_all:
                return func

            # otherwise, execute the decorator
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                handler = args[0]
                span = self._apply_tracing(handler, list(attributes))

                try:
                    result = func(handler)

                    # if it has `add_done_callback` it's a Future,
                    # else, a normal method/function.
                    if callable(getattr(result, 'add_done_callback', None)):
                        result._request_handler = handler
                        result.add_done_callback(self._finish_tracing_callback)
                    else:
                        self._finish_tracing(handler)

                except Exception as exc:
                    self._finish_tracing(handler, error=exc)
                    raise

                return result

            return wrapper
        return decorator

    def _get_operation_name(self, handler):
        full_class_name = type(handler).__name__
        return full_class_name.rsplit('.')[-1] # package-less name.

    def _finish_tracing_callback(self, future):
        handler = getattr(future, '_request_handler', None)
        if handler is not None:
            error = future.exception()
            self._finish_tracing(handler, error=error)

    def _apply_tracing(self, handler, attributes):
        '''
        Helper function to avoid rewriting for middleware and decorator.
        Returns a new span from the request with logged attributes and 
        correct operation name from the func.
        '''
        operation_name = self._get_operation_name(handler)
        headers = handler.request.headers
        request = handler.request

        # start new span from trace info
        span = None
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS, headers)
            span = self._tracer.start_span(operation_name=operation_name, child_of=span_ctx)
        except (opentracing.InvalidCarrierException, opentracing.SpanContextCorruptedException) as e:
            span = self._tracer.start_span(operation_name=operation_name)

        # add span to current spans 
        self._current_spans[request] = span

        # log any traced attributes
        span.set_tag('component', 'tornado')
        span.set_tag('http.method', request.method)
        span.set_tag('http.url', request.uri)

        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    span.set_tag(attr, payload)

        # invoke the start span callback, if any
        if self._start_span_cb is not None:
            self._start_span_cb(span, request)

        return span

    def _finish_tracing(self, handler, error=None):
        span = self._current_spans.pop(handler.request, None)
        if span is None:
            return

        if error is not None:
            span.set_tag('error', 'true')
            span.set_tag('error.object', error)

        span.set_tag('http.status_code', handler.get_status())

        span.finish()
