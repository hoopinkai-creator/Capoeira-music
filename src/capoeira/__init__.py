"""Capoeira Music — notation + living course pipeline.

The package is split so the pure-Python core (notation, course, config) imports
with no heavy dependencies. Audio/speech/AI/render modules import their extras
lazily and raise a clear message if an optional dependency is missing.
"""

__version__ = "0.1.0"
