from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version(__name__)
except PackageNotFoundError:
    __version__: str = "unknown"

from . import sub
from .app import Alfort, Dispatch, Effect, Enqueue, Init, Update, View

__all__ = [
    "Alfort",
    "Dispatch",
    "Effect",
    "View",
    "Update",
    "Init",
    "Enqueue",
    "sub",
]
