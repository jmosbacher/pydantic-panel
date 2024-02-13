import param
import datetime
import annotated_types

from typing import Any, Optional
from pydantic.fields import FieldInfo

try:
    from typing import _LiteralGenericAlias
except ImportError:
    _LiteralGenericAlias = None

from plum import dispatch
from numbers import Integral, Number
from panel import Param, Column


from panel.widgets import (
    Widget,
    LiteralInput,
    IntInput,
    NumberInput,
    DatetimePicker,
    Checkbox,
    TextInput,
    TextAreaInput,
    Select,
    MultiChoice,
)


ListInput = type("ListInput", (LiteralInput,), {"type": list})
DictInput = type("DictInput", (LiteralInput,), {"type": dict})
TupleInput = type("TupleInput", (LiteralInput,), {"type": tuple})


def clean_kwargs(obj: param.Parameterized,
                 kwargs: dict[str,Any]) -> dict[str,Any]:
    '''Remove any kwargs that are not explicit parameters of obj.
    '''
    return {k: v for k, v in kwargs.items() if k in obj.param.values()}


@dispatch
def infer_widget(value: Any, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    """Fallback function when a more specific
    function was not registered.
    """

    if field is not None and type(field.annotation) == _LiteralGenericAlias:
        options = list(field.annotation.__args__)
        if value not in options:
            value = options[0]
        options = kwargs.pop("options", options)
        kwargs = clean_kwargs(Select, kwargs)

        return Select(value=value, options=options, **kwargs)

    kwargs = clean_kwargs(LiteralInput, kwargs)
    return LiteralInput(value=value, **kwargs)


@dispatch
def infer_widget(value: Integral, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    start = None
    end = None
    if field is not None:
        if type(field.annotation) == _LiteralGenericAlias:
            options = list(field.annotation.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)

        for m in field.metadata:
            if isinstance(m, annotated_types.Gt):
                start = m.gt + 1
            if isinstance(m, annotated_types.Ge):
                start = m.ge
            if isinstance(m, annotated_types.Lt):
                end = m.lt - 1
            if isinstance(m, annotated_types.Le):
                end = m.le

    kwargs = clean_kwargs(IntInput, kwargs)
    return IntInput(value=value, start=start, end=end, **kwargs)


@dispatch
def infer_widget(value: Number, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    start = None
    end = None
    if field is not None:
        if type(field.annotation) == _LiteralGenericAlias:
            options = list(field.annotation.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)

        for m in field.metadata:
            if isinstance(m, annotated_types.Gt):
                start = m.gt + 1
            if isinstance(m, annotated_types.Ge):
                start = m.ge
            if isinstance(m, annotated_types.Lt):
                end = m.lt - 1
            if isinstance(m, annotated_types.Le):
                end = m.le

    kwargs = clean_kwargs(NumberInput, kwargs)
    return NumberInput(value=value, start=start, end=end, **kwargs)


@dispatch
def infer_widget(value: bool, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    if value is None:
        value = False
    kwargs = clean_kwargs(Checkbox, kwargs)
    return Checkbox(value=value, **kwargs)


@dispatch
def infer_widget(value: str, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    min_length = kwargs.pop("min_length", None)
    max_length = kwargs.pop("max_length", 100)

    if field is not None:
        if type(field.annotation) == _LiteralGenericAlias:
            options = list(field.annotation.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)
        for m in field.metadata:
            if isinstance(m, annotated_types.MinLen):
                min_length = m.min_length
            if isinstance(m, annotated_types.MaxLen):
                max_length = m.max_length

    kwargs["min_length"] = min_length

    if max_length is not None and max_length < 100:
        kwargs = clean_kwargs(TextInput, kwargs)
        return TextInput(value=value, max_length=max_length, **kwargs)

    kwargs = clean_kwargs(TextAreaInput, kwargs)
    return TextAreaInput(value=value, max_length=max_length, **kwargs)


@dispatch
def infer_widget(value: list, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    if field is not None and type(field.annotation) == _LiteralGenericAlias:
        options = list(field.annotation.__args__)
        if value not in options:
            value = []
        kwargs = clean_kwargs(ListInput, kwargs)
        return MultiChoice(name=field.alias, 
                           value=value, options=options)

    kwargs = clean_kwargs(ListInput, kwargs)
    return ListInput(value=value, **kwargs)


@dispatch
def infer_widget(value: dict, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    kwargs = clean_kwargs(DictInput, kwargs)
    return DictInput(value=value, **kwargs)


@dispatch
def infer_widget(value: tuple, field: Optional[FieldInfo] = None, **kwargs) -> Widget:
    kwargs = clean_kwargs(TupleInput, kwargs)
    return TupleInput(value=value, **kwargs)


@dispatch
def infer_widget(
    value: datetime.datetime, field: Optional[FieldInfo] = None, **kwargs
):
    kwargs = clean_kwargs(DatetimePicker, kwargs)
    return DatetimePicker(value=value, **kwargs)


@dispatch
def infer_widget(
    value: param.Parameterized, field: Optional[FieldInfo] = None, **kwargs
):
    kwargs = clean_kwargs(Param, kwargs)
    return Param(value, **kwargs)


@dispatch
def infer_widget(
    value: list[param.Parameterized], field: Optional[FieldInfo] = None, **kwargs
):
    kwargs = clean_kwargs(Param, kwargs)
    return Column(*[Param(val, **kwargs) for val in value])
