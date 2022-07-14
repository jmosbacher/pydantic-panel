#!/usr/bin/env python
"""Tests for `pydantic_panel` package."""
# pylint: disable=redefined-outer-name

import pydantic_panel
import pytest
import panel as pn
from pydantic import BaseModel


class SomeModel(BaseModel):
    regular_string: str = "string"
    regular_int: int = 42
    regular_float: float = 0.999


def test_panel_model_class():
    w = pn.panel(SomeModel)
    assert isinstance(w, pydantic_panel.PydanticModelEditor)
    assert w.value == SomeModel()


def test_panel_model_class_card():
    w = pn.panel(SomeModel, default_layout=pn.Card)
    assert isinstance(w, pydantic_panel.PydanticModelEditorCard)
    assert w.value == SomeModel()


def test_panel_model_instance():
    w = pn.panel(SomeModel())
    assert isinstance(w, pydantic_panel.PydanticModelEditor)
    assert w.value == SomeModel()


def test_panel_model_instalce_card():
    w = pn.panel(SomeModel(), default_layout=pn.Card)
    assert isinstance(w, pydantic_panel.PydanticModelEditorCard)
    assert w.value == SomeModel()
