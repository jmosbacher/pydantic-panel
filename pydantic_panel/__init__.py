"""Top-level package for pydantic-panel."""

__author__ = """Yossi Mosbacher"""
__email__ = "joe.mosbacher@gmail.com"
__version__ = "0.1.2"

from .dispatchers import json_serializable, get_widget
from .widgets import (
    PydanticModelEditor,
    PydanticModelEditorCard,
    PydanticModelListEditor,
)
from .pane import Pydantic
