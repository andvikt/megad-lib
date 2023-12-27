import asyncio
import contextlib
import functools
import heapq
import inspect
import pathlib
import pickle
import typing
from time import time

P = typing.ParamSpec("P")
R = typing.TypeVar("R")
R_ = typing.TypeVar("R_")
K = typing.TypeVar("K")
T = typing.TypeVar("T")


AsyncCalable = typing.Callable[P, typing.Coroutine[None, None, R]]
AsyncDecorator = typing.Callable[
    [typing.Callable[P, typing.Coroutine[None, None, R]]],
    typing.Callable[P, typing.Coroutine[None, None, R]],
]


class NotSet:
    pass


NOTSET = NotSet()


KeyBuilder = typing.Callable[[dict[str, typing.Any]], str]


TCtx = typing.TypeVar("TCtx", bound="_Ctx")


class _Ctx(typing.Protocol):
    async def start(self) -> None:
        ...

    async def __aenter__(self: TCtx) -> TCtx:
        ...


class BaseCache(_Ctx, typing.Protocol[R]):
    @staticmethod
    def default_factory(kwargs: dict[str, typing.Any]) -> str:
        return f'{".".join("{x}={y}" for x, y in kwargs.items())}'

    async def get(self, key: str) -> R | NotSet:
        raise NotImplementedError()

    async def set(self, key: str, value: R) -> None:
        raise NotImplementedError()

    async def reset(self, key: str) -> None:
        raise NotImplementedError()

    async def expire(self, key: str, ttl: float) -> None:
        raise NotImplementedError()

    def cached(
        self,
        template: str = None,
        ttl: float = None,
        key_factory: KeyBuilder | None = default_factory,
    ) -> typing.Callable[
        [typing.Callable[P, typing.Coroutine[None, None, R_]]],
        typing.Callable[P, typing.Coroutine[None, None, R_]],
    ]:
        """Decorator, makes function cached.

        Args:
            template (str, optional): template for key building, if None, default
            buider is used.
            ttl (float, optional): _description_. Defaults to None.
            key_factory (KeyBuilder | None, optional): Key factory, it is used template
            is None. It must be a function, that receives single argument of
            dic[str, Any] type, that is constructed from function arguments.
            Defaults to default_factory.
        """

        def deco(
            foo: typing.Callable[P, typing.Coroutine[None, None, R_]]
        ) -> typing.Callable[P, typing.Coroutine[None, None, R_]]:
            assert key_factory or template, "either key_factory or template is defined"
            params = list(inspect.signature(foo).parameters.values())

            @functools.wraps(foo)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R_:
                if template:
                    key = _get_key(template, params, *args, **kwargs)
                elif key_factory:
                    key = key_factory(_get_values(params, *args, **kwargs))
                r: R_ | NotSet = await self.get(key)  # type: ignore
                if isinstance(r, NotSet):
                    r = await foo(*args, **kwargs)
                    await self.set(key, r)  # type: ignore
                if ttl:
                    await self.expire(key, ttl)
                return r

            return wrapper

        return deco

    async def start(self) -> None:
        raise NotImplementedError()

    async def stop(self) -> None:
        raise NotADirectoryError()

    async def __aenter__(self: TCtx) -> TCtx:
        await self.start()
        return self

    async def __aexit__(self, exc_type: typing.Any, exc: typing.Any, tb: typing.Any) -> None:
        await self.stop()


class MemoryCache(BaseCache[R]):
    def __init__(
        self,
        store_factory: typing.Callable[[], typing.MutableMapping[str, typing.Any]] = None,
        persist_path: str = None,
    ) -> None:
        """Simple memory cache. It keeps all objects as key-value pairs in simple
        python dict. It also supports expiration.

        Args:
            persist_path (os.PathLike, optional): persists cache to file when closed.
            All objects must be picklable in that case.
        """
        store_factory = store_factory or dict
        super().__init__()
        self._data: typing.MutableMapping[str, R] = store_factory()
        self._real_expire: dict[str, float] = {}
        self._expire_task: asyncio.Task[None] | None = None
        self._exp_que: list[tuple[float, str]] = []
        self._lck = asyncio.Lock()
        self._persist = persist_path

    async def get(self, key: str) -> typing.Any | NotSet:
        return self._data.get(key, NOTSET)

    async def set(self, key: str, value: R) -> None:
        self._data[key] = value

    async def reset(self, key: str) -> None:
        del self._data[key]

    async def _wait_expire(self) -> None:
        try:
            while len(self._exp_que):
                _expire, key = heapq.heappop(self._exp_que)
                _ttl = _expire - time()
                if _ttl > 0:
                    await asyncio.sleep(_ttl)
                    # check if real expiration have changed
                    e = self._real_expire.get(key, None)
                    if e and e > time():
                        continue
                await self.reset(key)
        except asyncio.CancelledError:
            _ttl = _expire - time()
            if _ttl > 0:
                heapq.heappush(self._exp_que, (_ttl, key))
            return

    async def expire(self, key: str, ttl: float) -> None:
        self._real_expire[key] = _ttl = time() + ttl
        heapq.heappush(self._exp_que, (_ttl, key))
        async with self._lck:
            if self._expire_task:
                self._expire_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._expire_task

            self._expire_task = asyncio.create_task(self._wait_expire())

    async def start(self) -> None:
        if self._persist and pathlib.Path(self._persist).exists():
            with open(self._persist, "br") as f:
                self._data, self._exp_que, self._real_expire = pickle.load(f)
                self._expire_task = asyncio.create_task(self._wait_expire())
        return

    async def stop(self) -> None:
        if self._persist:
            with open(self._persist, "bw") as f:
                pickle.dump((self._data, self._exp_que, self._real_expire), f)
        async with self._lck:
            self._data.clear()
            self._exp_que.clear()
            self._real_expire.clear()
            if self._expire_task:
                self._expire_task.cancel()
                self._expire_task = None
        return


def _get_values(params: list[inspect.Parameter], *args: typing.Any, **kwargs: typing.Any) -> dict[str, typing.Any]:
    ret = kwargs.copy()
    for i, x in enumerate(args):
        ret[params[i].name] = x
    for x in params:
        if x.default is not inspect.Parameter.empty and x.name not in ret:
            ret[x.name] = x.default
    return ret


def _get_key(
    template: str,
    params: list[inspect.Parameter],
    *args: typing.Any,
    **kwargs: typing.Any,
) -> str:
    _params = _get_values(params, *args, **kwargs)
    try:
        return template.format_map(_params)
    except KeyError as exc:
        raise KeyError(f"bad key template: {exc} undefined in original function") from exc
