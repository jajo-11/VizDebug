"""
As I am not aware of any plugin system for the python debugger that allows triggering
function calls on stop of the debugger this plugin works by adding a call to this hook
to the watches.

Add this file to the path, make sure orjson is imported
Then add a watch `__import__("python_plugin").debug_viz_hook("SOME_NAME")`
"""

import inspect
import socket
from typing import Dict, Literal, Any
from itertools import chain

import numpy as np
from orjson import dumps, OPT_SERIALIZE_NUMPY


def send_dict(name: str, d: Dict[str, Any]):
    msg = dumps({"identity": name, "vars": d}, option=OPT_SERIALIZE_NUMPY)
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.connect(("::1", 4444))
    sock.send(len(msg).to_bytes(4, byteorder="big", signed=False) + msg)
    sock.close()


def add_serializable(d: Dict[str, Any], n: str, v: Any):
    if inspect.isfunction(v):
        return
    elif n.startswith("__"):
        return
    match v:
        case int() | float() | bool() | str() | list() | tuple() | dict():
            d[n] = v
        case np.ndarray():
            d[n] = np.ascontiguousarray(v)
        case _:
            pass


def debug_viz_hook(name: str) -> Literal["OK", "No Frame"]:
    this_frame = inspect.currentframe()
    if this_frame is None:
        return "No Frame"
    frame = this_frame.f_back
    if frame is None:
        return "No Frame"
    vars = dict[str, Any]()
    if (self_var := frame.f_locals.get("self")) is not None:
        self_vars = dict["str", Any]()
        for n, var in inspect.getmembers(self_var):
            add_serializable(self_vars, n, var)
        vars["self"] = self_vars
    for n, var in chain(frame.f_locals.items(), frame.f_globals.items()):
        add_serializable(vars, n, var)

    send_dict(name, vars)
    return "OK"
