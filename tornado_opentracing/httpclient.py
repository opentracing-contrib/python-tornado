from tornado.httpclient import HTTPRequest, HTTPError

import opentracing


g_tracing_disabled = True
g_client_tracer = None
g_start_span_cb = None


def _set_tracing_enabled(value):
    global g_tracing_disabled
    g_tracing_disabled = not value


def _set_tracing_info(tracer, start_span_cb):
    global g_client_tracer, g_start_span_cb
    g_client_tracer = tracer
    g_start_span_cb = start_span_cb


def _normalize_request(args, kwargs):
    req = args[0]
    if not isinstance(req, str):
        # Not a string, no need to force the creation of a HTTPRequest
        return (args, kwargs)

    # keep the original kwargs for calling fetch()
    new_kwargs = {}
    for param in ('callback', 'raise_error'):
        if param in kwargs:
            new_kwargs[param] = kwargs.pop(param)

    req = HTTPRequest(req, **kwargs)
    new_args = [req]
    new_args.extend(args[1:])

    # return the normalized args/kwargs
    return (new_args, new_kwargs)


def fetch_async(func, handler, args, kwargs):
    # Return immediately if disabled, no args were provided (error)
    # or original_request is set (meaning we are in a redirect step).
    if g_tracing_disabled or len(args) == 0 \
            or hasattr(args[0], 'original_request'):
        return func(*args, **kwargs)

    # Force the creation of a HTTPRequest object if needed,
    # so we can inject the context into the headers.
    args, kwargs = _normalize_request(args, kwargs)
    request = args[0]

    span = g_client_tracer.start_span(request.method)
    span.set_tag('component', 'tornado')
    span.set_tag('span.kind', 'client')
    span.set_tag('http.url', request.url)
    span.set_tag('http.method', request.method)

    g_client_tracer.inject(span.context,
                           opentracing.Format.HTTP_HEADERS,
                           request.headers)

    if g_start_span_cb:
        g_start_span_cb(span, request)

    future = func(*args, **kwargs)
    future._span = span
    future.add_done_callback(_finish_tracing_callback)

    return future


def _finish_tracing_callback(future):
    span = future._span
    status_code = None

    exc = future.exception()
    if exc:
        # Tornado uses HTTPError to report some of the
        # codes other than 2xx, so check the code is
        # actually in the 5xx range - and include the
        # status code for *all* HTTPError instances.
        error = True
        if isinstance(exc, HTTPError):
            status_code = exc.code
            if status_code < 500:
                error = False

        if error:
            span.set_tag('error', 'true')
            span.set_tag('error.object', exc)
    else:
        status_code = future.result().code

    if status_code is not None:
        span.set_tag('http.status_code', status_code)

    span.finish()
