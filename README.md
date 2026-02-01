# Viz Debug

This is a small gadget that integrates with gdb, allowing you to plot arrays with minimal hassle. I wrote this to debug a port of an existing program, so you can easily connect two debuggers to the same plot window, allowing you to plot things like array_a - array_b and similar.

# Usage
- Run viz debug `python -m VizDebug`
- call plugins/gdb.py from gdb
- step with gdb
- enter a python expression into the text field, numpy is imported as np. Any 1d array result will be plotted. You can access variables of the debugee via executable_name["var_name"]

# Limitations
Everything is barebone right now but possibility the biggest limitation right now is that structs are not supported (I am debugging very unstructured fortran that does not have them).