"""
pydantic-panel makes it easy to combine Pydantic and Panel
==========================================================

With pydantic-panel you can

- edit Pydantic models in notebooks and data apps.
- build data apps from Pydantic Models using the dataviz tools you already know
and love ❤️.

To learn more check out https://pydantic-panel.readthedocs.io/en/latest/. To
report issues or contribute go to https://github.com/jmosbacher/pydantic-panel.

How to use pydantic-panel in 3 simple steps
-------------------------------------------

1. Define your Pydantic model

>>> import pydantic
>>> class SomeModel(pydantic.BaseModel):
...    name: str
...    value: float

2. Import panel and pydantic_panel

>>> import panel as pn
>>> import pydantic_panel
>>> pn.extension()

3. Wrap your model with `pn.panel` and work with Panel as you normally would

>>> widget = pn.panel(SomeModel)
>>> layout = pn.Column(widget, widget.json)
>>> layout.servable()

In a notebook this will give you a component with widgets for editing your
model.

You can also serve this as a data app if you run `panel serve
name_of_file.ipynb --show` (or `panel serve name_of_file.py --show`). Add
the `--autoreload` flag for hot reloading during development.
"""

__author__ = """Yossi Mosbacher"""
__email__ = "joe.mosbacher@gmail.com"
__version__ = "0.1.12"

from .dispatchers import json_serializable, infer_widget
from .widgets import (
    PydanticModelEditor,
    PydanticModelEditorCard,
    ItemListEditor,
    ItemDictEditor,
)

# Needed for VS Code/ pyright to discover the available items
__all__ = [
    "infer_widget",
    "ItemDictEditor",
    "ItemListEditor",
    "json_serializable",
    "PydanticModelEditor",
    "PydanticModelEditorCard",
]


def extension(load_panel=True):
    # FIXME: make a settings object
    # that can control how Pydantic behaves
    # and can be set here
    from .pane import Pydantic
    
    __all__.append('Pydantic')

    if load_panel:
        import panel as pn
        pn.extension()


