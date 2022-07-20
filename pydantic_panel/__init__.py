"""Top-level package for pydantic-panel."""

__author__ = """Yossi Mosbacher"""
__email__ = "joe.mosbacher@gmail.com"
__version__ = "0.1.4"

from .dispatchers import json_serializable, get_widget
from .widgets import (
    PydanticModelEditor,
    PydanticModelEditorCard,
    ItemListEditor,
    ItemDictEditor,
)
from .pane import Pydantic
