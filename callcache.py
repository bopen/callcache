import datetime
import functools
import hashlib
import importlib
import inspect
import json
import operator
import uuid

import xarray as xr


def uniquify_arguments(callable_, *args, **kwargs):
    try:
        bound_arguments = inspect.signature(callable_).bind(*args, **kwargs)
        bound_arguments.apply_defaults()
        args, kwargs = bound_arguments.args, bound_arguments.kwargs
    except:
        pass
    sorted_kwargs = sorted(kwargs.items(), key=operator.itemgetter(0))
    return args, dict(sorted_kwargs)


def inspect_fully_qualified_name(obj):
    """Return the fully qualified name of a python object."""
    module = inspect.getmodule(obj)
    return f"{module.__name__}:{obj.__qualname__}"


def import_object(fully_qualified_name):
    if ":" not in fully_qualified_name:
        raise ValueError(f"{fully_qualified_name} not in the form 'module:qualname'")
    module_name, _, object_name = fully_qualified_name.partition(":")
    obj = importlib.import_module(module_name)
    for attr_name in object_name.split("."):
        obj = getattr(obj, attr_name)
    return obj


def uniquify_call_signature(callable_, *args, **kwargs):
    if isinstance(callable_, str):
        fully_qualified_name = callable_
    else:
        fully_qualified_name = inspect_fully_qualified_name(callable_)
    args, kwargs = uniquify_arguments(callable_, *args, **kwargs)
    call_signature = {"callable": fully_qualified_name}
    if args:
        call_signature["args"] = args
    if kwargs:
        call_signature["kwargs"] = kwargs
    return call_signature


def filecache_default(o):
    if isinstance(o, datetime.datetime):
        return uniquify_call_signature("datetime:datetime.fromisoformat", o.isoformat())
    elif isinstance(o, xr.Dataset):
        try:
            path = o.encoding["source"]
            orig = xr.open_dataset(path)
            if not o.identical(orig):
                path = None
        except:
            path = None
        if path is None:
            path = f"./{uuid.uuid4()}.nc"
            o.to_netcdf(path)
        call_signature = {"type": "object/constructor"}
        call_signature.update(uniquify_call_signature(xr.open_dataset, path))
        return call_signature
    raise TypeError("can't encode object")


def call(callable, args=(), kwargs={}):
    func = import_object(callable)
    return func(*args, **kwargs)


def call_json(call_signature_json):
    call_signature = json.loads(call_signature_json)
    return call(**call_signature)


def call_object_hook(o):
    if o.pop("type", None) == "object/constructor" and "callable" in o:
        return call(**o)
    return o


def jsonify(obj):
    return json.dumps(obj, separators=(",", ":"), default=filecache_default)


def uniquify_call_signature_json(callable_, *args, **kwargs):
    unique_call_signature = uniquify_call_signature(callable_, *args, **kwargs)
    return jsonify(unique_call_signature)


def hexdigestify(text):
    hash_req = hashlib.sha3_224(text.encode())
    return hash_req.hexdigest()


def uniquify_call_signatures(callable_, *args, **kwargs):
    call_signature = uniquify_call_signature(callable_, *args, **kwargs)
    call_signature_json = jsonify(call_signature)
    return call_signature, call_signature_json, hexdigestify(call_signature_json)


CACHE = {}


def invalidate_entry(hexdigest):
    return CACHE.pop(hexdigest, None)


def cacheable(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            signatures = uniquify_call_signatures(func, *args, **kwargs)
        except TypeError:
            print(f"UNCACHEABLE: {args} {kwargs}")
            return func(*args, **kwargs)

        signature_dict, signature_json, hexdigest = signatures
        if hexdigest not in CACHE:
            print(f"MISS: {hexdigest} {signature_json}")
            result = func(*signature_dict["args"], **signature_dict["kwargs"])
            CACHE[hexdigest] = (signature_json, result)
        else:
            print(f"HIT: {hexdigest}")
        return CACHE[hexdigest][1]

    return wrapper
