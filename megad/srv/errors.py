from typing import Any, Protocol

import orjson
from aiohttp import web


class _ExcFactory(Protocol):
    def __call__(data: Any | None = None) -> Exception:
        ...


def err(err_code: int, description: str = None) -> _ExcFactory:
    _body = orjson.dumps({"err_code": err_code, "description": description})
    err_code = err_code
    description = description

    class ClientError(web.HTTPBadRequest):
        def __init__(self, data: Any | None = None) -> None:
            body = _body
            if data:
                body = orjson.dumps({"err_code": err_code, "description": description, "data": data})
            super().__init__(body=body)

    return ClientError


BadPasswordError = err(0, "bad password")
ParsingError = err(1, "parsing error")
VesionNotFoundError = err(3, "version not found")
NoSuchController = err(4, "no such controller")
