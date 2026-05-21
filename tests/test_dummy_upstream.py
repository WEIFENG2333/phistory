from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phistory.dummy_upstream import dummy_upstream


def test_dummy_upstream_returns_401():
    with dummy_upstream() as base_url:
        req = Request(f"{base_url}/v1/messages", data=b'{"ok":true}', method="POST")
        try:
            urlopen(req, timeout=5)
        except HTTPError as exc:
            assert exc.code == 401
            assert b"phistory dummy upstream" in exc.read()
        else:
            raise AssertionError("expected HTTPError")
