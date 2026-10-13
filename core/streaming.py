"""Serve a stored file with HTTP Range support, so <video> can seek. Access checks are the caller's job."""

import re

from django.http import HttpResponse, StreamingHttpResponse

CHUNK = 1024 * 1024
_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


def ranged_file_response(request, fieldfile, content_type):
    size = fieldfile.size
    start, end, status = 0, size - 1, 200
    match = _RANGE.match(request.headers.get("Range", "").strip())
    if match and (match[1] or match[2]):  # a malformed Range header is ignored (RFC 9110): full response
        if match[1]:
            start = int(match[1])
            end = min(int(match[2]), size - 1) if match[2] else size - 1
        else:  # "bytes=-N": the last N bytes
            start, end = max(0, size - int(match[2])), size - 1
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        status = 206
    length = end - start + 1

    def iterate():
        with fieldfile.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                data = handle.read(min(CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    response = StreamingHttpResponse(iterate(), status=status, content_type=content_type)
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
