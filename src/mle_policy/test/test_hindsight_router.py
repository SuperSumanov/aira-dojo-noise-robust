"""Input: local mock HTTP servers. Output: assertions; no data files or GPU use."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import gzip
import json

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest
from yarl import URL

from src.mle_policy.src.data.hindsight.router import create_app


@asynccontextmanager
async def running_router(handlers):
    async with AsyncExitStack() as stack:
        backends = []
        for handler in handlers:
            app = web.Application(client_max_size=0, handler_args={"auto_decompress": False})
            app.router.add_route("*", "/v1/{path:.*}", handler)
            server = await stack.enter_async_context(TestServer(app))
            backends.append(str(server.make_url("/")))
        client = await stack.enter_async_context(
            TestClient(TestServer(create_app(backends), handler_cancellation=True))
        )
        yield client, backends


async def counts(client):
    async with client.get("/health") as response:
        return [backend["in_flight"] for backend in (await response.json())["backends"]]


@pytest.mark.parametrize("status", [200, 401, 429, 500])
@pytest.mark.parametrize("compressed", [False, True])
def test_proxy_preserves_large_body_auth_query_status_and_encoding(status, compressed):
    async def exercise():
        payload = json.dumps({"model": "shared-model", "prompt": "long context" * 120000}).encode()
        if compressed:
            payload = gzip.compress(payload)
        received = []

        async def echo(request):
            received.append((request.raw_path, dict(request.headers), await request.read()))
            headers = {
                "Content-Type": "application/json",
                "Connection": "X-Upstream-Hop",
                "X-Upstream-Hop": "remove",
                "X-Request-ID": "upstream-id",
            }
            if compressed:
                headers["Content-Encoding"] = "gzip"
            return web.Response(body=payload, status=status, headers=headers)

        async with running_router([echo]) as (client, backends):
            headers = {
                "Authorization": "Bearer existing-key",
                "Content-Type": "application/json",
                "Connection": "X-Client-Hop",
                "X-Client-Hop": "remove",
            }
            if compressed:
                headers["Content-Encoding"] = "gzip"
            async with client.post(
                URL("/v1/chat/completions?name=a%2Fb", encoded=True),
                data=payload,
                headers=headers,
                auto_decompress=False,
            ) as response:
                assert response.status == status
                assert await response.read() == payload
                assert response.headers["X-Request-ID"] == "upstream-id"
                assert "X-Upstream-Hop" not in response.headers
                assert response.headers.get("Content-Encoding") == ("gzip" if compressed else None)
            path, headers, body = received[0]
            assert path == "/v1/chat/completions?name=a%2Fb"
            assert headers["Authorization"] == "Bearer existing-key"
            assert headers["Host"] == backends[0].removeprefix("http://").rstrip("/")
            assert "X-Client-Hop" not in headers
            assert body == payload
            assert await counts(client) == [0]

    asyncio.run(exercise())


def test_equal_load_rotates_across_all_replicas():
    async def exercise():
        selected = []

        def handler(index):
            async def models(request):
                selected.append(index)
                return web.json_response({"data": [{"id": "shared-model"}]})

            return models

        async with running_router([handler(index) for index in range(3)]) as (client, _):
            for _ in range(6):
                async with client.get("/v1/models") as response:
                    assert (await response.json())["data"][0]["id"] == "shared-model"
            assert selected == [0, 1, 2, 0, 1, 2]
            assert await counts(client) == [0, 0, 0]

    asyncio.run(exercise())


def test_stream_remains_in_flight_and_new_requests_use_idle_replica():
    async def exercise():
        release = asyncio.Event()
        fast_requests = []

        async def slow(request):
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            await response.write(b'data: {"reasoning_content":"thinking"}\n\n')
            await release.wait()
            await response.write(b"data: [DONE]\n\n")
            return response

        async def fast(request):
            fast_requests.append(await request.json())
            return web.json_response({"choices": [{"message": {"content": "answer"}}]})

        async with running_router([slow, fast]) as (client, _):
            try:
                async with client.post("/v1/chat/completions", json={"stream": True}) as response:
                    async with asyncio.timeout(5):
                        assert await response.content.readuntil(b"\n\n") == (
                            b'data: {"reasoning_content":"thinking"}\n\n'
                        )
                    assert await counts(client) == [1, 0]
                    for _ in range(3):
                        async with client.post("/v1/chat/completions", json={"stream": False}) as short:
                            assert (await short.json())["choices"][0]["message"]["content"] == "answer"
                    assert len(fast_requests) == 3
                    assert await counts(client) == [1, 0]
                    release.set()
                    assert await response.read() == b"data: [DONE]\n\n"
                assert await counts(client) == [0, 0]
            finally:
                release.set()

    asyncio.run(exercise())


def test_client_disconnect_releases_count():
    async def exercise():
        release = asyncio.Event()

        async def slow(request):
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            await response.write(b"data: first\n\n")
            await release.wait()
            return response

        async with running_router([slow]) as (client, _):
            try:
                response = await client.post("/v1/chat/completions", json={"stream": True})
                await response.content.readuntil(b"\n\n")
                assert await counts(client) == [1]
                response.close()
                async with asyncio.timeout(5):
                    while await counts(client) != [0]:
                        await asyncio.sleep(0.01)
            finally:
                release.set()

    asyncio.run(exercise())


def test_connection_failure_returns_502_and_releases_count():
    async def exercise():
        server = TestServer(web.Application())
        await server.start_server()
        url = str(server.make_url("/"))
        await server.close()
        async with TestClient(TestServer(create_app([url]))) as client:
            async with client.post("/v1/chat/completions", json={"model": "shared-model"}) as response:
                assert response.status == 502
                assert url.rstrip("/") in await response.text()
            assert await counts(client) == [0]

    asyncio.run(exercise())
