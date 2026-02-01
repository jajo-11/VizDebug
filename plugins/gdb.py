"""
Load this file in your gdb session to send variables to the viz_debugger on every stop

If you use VSCode you can add it to your launch.json configuration by adding an option like this

```json
    "setupCommands": [
    {
        "description": "Load export script",
        "text": "source /path/to/viz_debug/plugins/gdb.py",
        "ignoreFailures": false
    }
    ],
```
"""

import gdb

import socket
from os import path
from typing import Any, Dict
from json import dumps


def send_dict(name: str, d: Dict[str, Any]):
    msg = dumps({"identity": name, "vars": d}).encode()
    # gdb.write(msg.decode())
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.connect(("::1", 4444))
    sock.send(len(msg).to_bytes(4, byteorder="big", signed=False) + msg)
    sock.close()


gdb_to_python: Dict[int, type] = {
    gdb.TYPE_CODE_BOOL: bool,
    gdb.TYPE_CODE_INT: int,
    gdb.TYPE_CODE_FLT: float,
}


def gdb_value_to_python(value: gdb.Value) -> Any:
    if value.type.is_array_like:
        value: gdb.Value = value.to_array()
    match value.type.code:
        case gdb.TYPE_CODE_BOOL:
            return bool(value)
        case gdb.TYPE_CODE_CHAR:
            return chr(value)
        case gdb.TYPE_CODE_FLT:
            return float(value)
        case gdb.TYPE_CODE_INT:
            return int(value)
        case gdb.TYPE_CODE_ARRAY:
            if target_type := gdb_to_python.get(value.type.target().code):
                start, stop = value.type.fields()[0].type.range()
                values = [target_type(value[i]) for i in range(start, stop)]
                return values
            return None
        case _:
            return None


def stop_handler(event: gdb.StopEvent):
    name = gdb.selected_inferior().progspace.executable_filename
    name = name or "Anon"
    name = path.basename(name)

    vars = dict[str, Any]()
    frame = gdb.selected_frame()
    block = frame.block()
    while block:
        for symbol in block:
            if symbol.is_argument or symbol.is_variable:
                vars[symbol.name] = gdb_value_to_python(symbol.value(frame))
        block = block.superblock

    # gdb.write(str(vars))
    send_dict(name, vars)


gdb.events.stop.connect(stop_handler)
