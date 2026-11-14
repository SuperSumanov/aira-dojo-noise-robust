"""Route OpenAI-compatible HTTP requests to the least-busy vLLM replica.

Input: --backends lists service roots such as http://127.0.0.1:8000 (without /v1).
Clients send /v1/* requests with the same model name and API key on every replica.
Output: HTTP responses, including streaming bodies; GET /health returns the local
in-flight counts. No input directories or output files; logs go to the console.
Run one router process so all requests share the same counters.
"""

import argparse

from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector, web
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL


def forward_headers(headers: CIMultiDictProxy[str]) -> CIMultiDict[str]:
    """Keep end-to-end headers while allowing each HTTP connection its own framing."""
    excluded = {
        "host",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
    for value in headers.getall("Connection", []):
        excluded.update(part.strip().lower() for part in value.split(","))
    return CIMultiDict((name, value) for name, value in headers.items() if name.lower() not in excluded)


def create_app(backends: list[str]) -> web.Application:
    """Build a single-process proxy with request counts held until response completion."""
    backends = [url.rstrip("/") for url in backends]
    in_flight = [0] * len(backends)
    next_backend = 0
    app = web.Application(client_max_size=0, handler_args={"auto_decompress": False})
    session_key = web.AppKey("session", ClientSession)

    async def session_context(app):
        async with ClientSession(
            connector=TCPConnector(limit=0),
            timeout=ClientTimeout(total=None, sock_connect=10, sock_read=14400),
            auto_decompress=False,
            trust_env=False,
        ) as session:
            app[session_key] = session
            yield

    async def health(request):
        return web.json_response(
            {"backends": [{"url": url, "in_flight": count} for url, count in zip(backends, in_flight)]}
        )

    async def forward(request):
        nonlocal next_backend
        body = await request.read()
        selected = min(
            range(len(backends)),
            key=lambda index: (in_flight[index], (index - next_backend) % len(backends)),
        )
        next_backend = (selected + 1) % len(backends)
        in_flight[selected] += 1
        try:
            try:
                upstream = await app[session_key].request(
                    request.method,
                    URL(backends[selected] + request.raw_path, encoded=True),
                    headers=forward_headers(request.headers),
                    data=body,
                    allow_redirects=False,
                )
            except (ClientError, TimeoutError) as error:
                raise web.HTTPBadGateway(text=f"{backends[selected]}: {error}") from error
            async with upstream:
                response = web.StreamResponse(status=upstream.status, headers=forward_headers(upstream.headers))
                await response.prepare(request)
                async for chunk in upstream.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
        finally:
            in_flight[selected] -= 1

    app.cleanup_ctx.append(session_context)
    app.router.add_get("/health", health)
    app.router.add_route("*", "/v1/{path:.*}", forward)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backends", nargs="+", required=True, help="vLLM service roots, without /v1")
    parser.add_argument("--host", default="127.0.0.1", help="Router bind address; use 0.0.0.0 for remote clients")
    parser.add_argument("--port", type=int, default=7999, help="Router listening port")
    args = parser.parse_args()
    web.run_app(create_app(args.backends), host=args.host, port=args.port, handler_cancellation=True, access_log=None)


if __name__ == "__main__":
    main()
