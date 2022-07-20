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

alt_data = dict(
    regular_string = "string2",
    regular_int = 666,
    regular_float = 0.111,
)

def test_panel_model_class():
    w = pn.panel(SomeModel)
    assert isinstance(w, pydantic_panel.PydanticModelEditor)
    assert w.value == SomeModel()


def test_panel_model_instance():
    w = pn.panel(SomeModel())
    assert isinstance(w, pydantic_panel.PydanticModelEditor)
    assert w.value == SomeModel()


def test_set_data():
    m = SomeModel()
    w = pn.panel(m)
    for k,v in alt_data.items():
        w._widgets[k].value = v
        assert getattr(w.value, k) == v
    assert w.value == m

def test_bidirectional():
    m = SomeModel()
    w = pn.panel(m, bidirectional=True)
    for k,v in alt_data.items():
        setattr(m, k, v)
        assert w._widgets[k].value == v
    assert w.value == m
