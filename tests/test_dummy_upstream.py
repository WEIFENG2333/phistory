import json
from urllib.request import Request, urlopen

from phistory.dummy_upstream import dummy_upstream


def test_dummy_upstream_returns_anthropic_success():
    with dummy_upstream() as base_url:
        req = Request(f"{base_url}/v1/messages", data=b'{"ok":true}', method="POST")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert b"msg_phistory_dummy" in resp.read()


def test_dummy_upstream_returns_openai_responses_success():
    with dummy_upstream() as base_url:
        req = Request(f"{base_url}/v1/responses", data=b'{"ok":true}', method="POST")
        with urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())

    assert body["status"] == "completed"
    assert body["output"][0]["content"][0]["text"] == "ok"


def test_dummy_upstream_returns_models_list():
    with dummy_upstream() as base_url:
        with urlopen(f"{base_url}/v1/models", timeout=5) as resp:
            body = json.loads(resp.read())

    assert body["object"] == "list"
    assert body["data"][0]["id"]
