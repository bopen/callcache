import pathlib

try:
    import netCDF4  # noqa
    import pandas as pd
    import xarray as xr
except ImportError:  # pragma: no cover
    xr = None


from . import cache
from . import encode


def dictify_xr_dataset(o, cache_root=".", file_name_template="{uuid}.nc"):
    # xarray >= 0.14.1 provide stable hashing
    uuid = cache.hexdigestify(str(o.__dask_tokenize__()))
    file_name = file_name_template.format(**locals())
    path = pathlib.Path(cache_root).absolute() / file_name
    try:
        orig = xr.open_dataset(path)
    except:
        orig = None
        o.to_netcdf(path)
    if orig is not None and not o.identical(orig):
        raise RuntimeError(f"inconsistent array in file {path}")
    return encode.dictify_python_call(xr.open_dataset, str(path))


def dictify_pd_dataframe(o, cache_root=".", file_name_template="{uuid}.csv"):
    import dask.base

    uuid = cache.hexdigestify(str(dask.base.normalize_token(o)))
    file_name = file_name_template.format(**locals())
    path = pathlib.Path(cache_root).absolute() / file_name
    try:
        orig = pd.read_csv(path)
    except:
        orig = None
        o.to_csv(path)
    # if orig is not None and not o.identical(orig):
    #    raise RuntimeError(f"inconsistent array in file {path}")
    return encode.dictify_python_call(pd.read_csv, str(path))


def register_all():
    if xr is not None:  # pragma: no cover
        encode.FILECACHE_ENCODERS.append((xr.Dataset, dictify_xr_dataset))