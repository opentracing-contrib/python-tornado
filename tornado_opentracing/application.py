# Copyright The OpenTracing Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from . import httpclient


DEFAULT_TRACE_ALL = True
DEFAULT_TRACE_CLIENT = True


def tracer_config(__init__, app, args, kwargs):
    """
    Wraps the Tornado web application initialization so that the
    TornadoTracing instance is created around an OpenTracing-compatible tracer.
    """
    __init__(*args, **kwargs)

    tracing = app.settings.get('opentracing_tracing')
    if tracing is None:
        return

    tracing._trace_all = app.settings.get('opentracing_trace_all',
                                          DEFAULT_TRACE_ALL)
    tracing._trace_client = app.settings.get('opentracing_trace_client',
                                             DEFAULT_TRACE_CLIENT)
    tracing._start_span_cb = app.settings.get('opentracing_start_span_cb',
                                              None)

    httpclient._set_tracing_enabled(tracing._trace_client)
    if tracing._trace_client:
        httpclient._set_tracing_info(tracing._tracer, tracing._start_span_cb)
