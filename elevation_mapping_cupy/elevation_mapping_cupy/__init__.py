from .parameter import Parameter


def __getattr__(name):
    if name == "ElevationMap":
        from .elevation_mapping import ElevationMap

        return ElevationMap
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Parameter", "ElevationMap"]
