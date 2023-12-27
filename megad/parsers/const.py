import re

PATT_FW = re.compile(r"fw:\s([0-9\.b]*)")
PATT_VAR_B = re.compile(r"var b=(.*?);")
PATT_VAR_C = re.compile(r"var c=(.*?);")
PATT_ALLOWED_NEXT = re.compile(r"\?(cf|pt)=")
PATT_DS2413_LIST = re.compile(r"(.*?):(ON|OFF)\/(ON|OFF)")

SKIP_PATHS = {
    "/?cf=9",
    "/?cf=7",
}
PATT_EXT230 = re.compile(r"P(\d{1,2}) - (OUT|IN)")
