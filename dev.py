from doctest import debug

from aiohttp import web
from cashews import cache
from megad.srv import get_app

cache.setup("mem://")
if __name__ == "__main__":
    web.run_app(get_app())
