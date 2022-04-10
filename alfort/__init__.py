try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version  # type: ignore

__version__ = version(__name__)
