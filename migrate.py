import asyncio
from megad.db.engine import async_rev


async def main() -> None:
    await async_rev("sqlite+aiosqlite:///test.sqlite")


asyncio.run(main())
