import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial, wraps
from logging import getLogger
from typing import Annotated, Any, ParamSpec, TypeVar, Union

import orjson
import pydantic
from aiohttp import web

from megad.db.engine import db_life

Q = TypeVar("Q")
T = TypeVar("T", bound=pydantic.BaseModel)
R = TypeVar("R", bound=pydantic.BaseModel | None, covariant=True)


class _Query:
    pass


class _Path:
    pass


Path = Annotated[Q, _Path]
Query = Annotated[Q, _Query]


_Param = _Query | _Path | pydantic.BaseModel

HandlerProto = Union[
    Callable[..., Awaitable[R]],
    Callable[[_Param], Awaitable[R]],
    Callable[[_Param, _Param], Awaitable[R]],
    Callable[[_Param, _Param, _Param], Awaitable[R]],
    Callable[[_Param, _Param, _Param, _Param], Awaitable[R]],
]


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class Router:
    def __init__(self) -> None:
        self.handlers: list[tuple[str, str, HandlerProto[Any]]] = []

    def route(self, method: str, path: str) -> Callable[[HandlerProto[R]], HandlerProto[R]]:
        def deco(foo: HandlerProto[R]) -> HandlerProto[R]:
            self.handlers.append((method, path, foo))
            return foo

        return deco

    def get(self, path: str) -> Callable[[HandlerProto[R]], HandlerProto[R]]:
        return self.route("get", path)

    def post(self, path: str) -> Callable[[HandlerProto[R]], HandlerProto[R]]:
        return self.route("post", path)


router = Router()


P = ParamSpec("P")
RR = TypeVar("RR")
lg = getLogger()


def _log_errors(foo: Callable[P, Awaitable[RR]]) -> Callable[P, Awaitable[RR]]:
    @wraps(foo)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> RR:
        try:
            return await foo(*args, **kwargs)
        except web.HTTPClientError:
            raise
        except Exception:
            lg.exception(f"{foo} ({args}, {kwargs})")
            raise

    return wrapper


def _make_aiohttp_handler(hm: HandlerProto[R]) -> Handler:  # noqa: C901
    """создает aiohttp-хендлер опираясь на функцию hm"""
    sig = inspect.signature(hm)
    params = list(sig.parameters.values())
    body_type: type[pydantic.BaseModel] | None = None
    body_key: str | None = None
    path_params: dict[str, inspect.Parameter] = {}
    query_params: dict[str, inspect.Parameter] = {}
    for x in params:
        if not x.annotation:
            raise ValueError(f"{hm} must have annotations")
        if isinstance(x.annotation, type) and issubclass(x.annotation, pydantic.BaseModel) and body_type is not None:
            raise ValueError(f"{hm} can have only one BaseModel parameter")
        elif isinstance(x.annotation, type) and issubclass(x.annotation, pydantic.BaseModel):
            body_type = x.annotation
            body_key = x.name
        elif hasattr(x.annotation, "__metadata__") and x.annotation.__metadata__:
            if x.annotation.__metadata__[0] is _Path:
                path_params[x.name] = x
            elif x.annotation.__metadata__[0] is _Query:
                query_params[x.name] = x
        else:
            raise ValueError(f"{x.annotation=} is not supported")

    @_log_errors
    async def handler(r: web.Request) -> web.StreamResponse:
        kwargs: dict[str, Any] = {}
        if body_type and body_key:
            raw = await r.read()
            kwargs[body_key] = body_type.parse_raw(raw)
        # get qury params
        for k, v in query_params.items():
            _v = r.query.get(k, v.default)
            if _v is inspect.Parameter.empty:  # type: ignore
                raise web.HTTPBadRequest(text=f"{k} query arg is empty")
            try:
                kwargs[k] = v.annotation(_v)
            except Exception as exc:
                raise web.HTTPBadRequest(text=f"{k}={_v} query arg is not parsed with {v.annotation}") from exc
        # get path params
        for k, v in path_params.items():
            _v = r.match_info.get(k, v.default)
            if _v is inspect.Parameter.empty:  # type: ignore
                raise web.HTTPBadRequest(text=f"{k} path arg is empty")
            try:
                kwargs[k] = v.annotation(_v)
            except Exception as exc:
                raise web.HTTPBadRequest(text=f"{k}={_v} query arg is not parsed with {v.annotation}") from exc

        ret = await hm(**kwargs)  # type: ignore
        if isinstance(ret, pydantic.BaseModel):
            response = web.Response(
                body=ret.json(exclude_none=True).encode(),
                content_type="application/json",
                status=200,
            )
            response.enable_compression()
            return response
        else:
            return web.Response(status=200)

    return handler


async def cleanup_ctx(uri: str, app: web.Application) -> AsyncIterator[Any]:
    async with db_life(uri, migrate=True):
        yield


def get_app(
    prefix: str = "",
    uri: str = "sqlite+aiosqlite:///test.sqlite",
    **kwargs: Any,
) -> web.Application:
    app = web.Application(**kwargs)
    app.cleanup_ctx.append(partial(cleanup_ctx, uri))
    app.add_routes(
        web.route(
            meth,
            f"{prefix}{path}",
            _make_aiohttp_handler(handler),
        )
        for (
            meth,
            path,
            handler,
        ) in router.handlers
    )

    return app


E = TypeVar("E", bound=web.HTTPClientError)


def err(t: type[E], text: str) -> E:
    return t(body=orjson.dumps({"description": text}))
