# conftest.py
import sys
from typing import Any, NoReturn

import pytest


def is_debugging() -> bool:
    if "debugpy" in sys.modules:
        return True
    return False


# enable_stop_on_exceptions if the debugger is running during a test
if is_debugging():

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: Any) -> NoReturn:
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: Any) -> NoReturn:
        raise excinfo.value
