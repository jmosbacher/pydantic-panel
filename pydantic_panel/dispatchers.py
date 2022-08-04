import param
import datetime
from typing import Dict, List, Any, Optional
from pydantic.fields import ModelField

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
                 kwargs: Dict[str,Any]) -> Dict[str,Any]:
    '''Remove any kwargs that are not explicit parameters of obj.
    '''
    return {k: v for k, v in kwargs.items() if k in obj.param.params()}


@dispatch
def infer_widget(value: Any, field: Optional[ModelField] = None, **kwargs) -> Widget:
    """Fallback function when a more specific
    function was not registered.
    """

    if field is not None and type(field.outer_type_) == _LiteralGenericAlias:
        options = list(field.outer_type_.__args__)
        if value not in options:
            value = options[0]
        options = kwargs.pop("options", options)
        kwargs = clean_kwargs(Select, kwargs)

        return Select(value=value, options=options, **kwargs)

    kwargs = clean_kwargs(LiteralInput, kwargs)
    return LiteralInput(value=value, **kwargs)


@dispatch
def infer_widget(value: Integral, field: Optional[ModelField] = None, **kwargs) -> Widget:
    start = None
    end = None
    if field is not None:
        if type(field.outer_type_) == _LiteralGenericAlias:
            options = list(field.outer_type_.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)

        start = getattr(field.field_info, "gt", None)
        if start is not None:
            start += 1
        else:
            start = getattr(field.field_info, "ge")

        end = getattr(field.field_info, "lt", None)
        if end is not None:
            end -= 1
        else:
            end = getattr(field.field_info, "le", None)
    kwargs = clean_kwargs(IntInput, kwargs)
    return IntInput(value=value, start=start, end=end, **kwargs)


@dispatch
def infer_widget(value: Number, field: Optional[ModelField] = None, **kwargs) -> Widget:
    start = None
    end = None
    if field is not None:
        if type(field.outer_type_) == _LiteralGenericAlias:
            options = list(field.outer_type_.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)

        start = getattr(field.field_info, "gt", None)
        end = getattr(field.field_info, "lt", None)
    kwargs = clean_kwargs(NumberInput, kwargs)
    return NumberInput(value=value, start=start, end=end, **kwargs)


@dispatch
def infer_widget(value: bool, field: Optional[ModelField] = None, **kwargs) -> Widget:
    if value is None:
        value = False
    kwargs = clean_kwargs(Checkbox, kwargs)
    return Checkbox(value=value, **kwargs)


@dispatch
def infer_widget(value: str, field: Optional[ModelField] = None, **kwargs) -> Widget:
    min_length = kwargs.pop("min_length", None)
    max_length = kwargs.pop("max_length", 100)

    if field is not None:
        if type(field.outer_type_) == _LiteralGenericAlias:
            options = list(field.outer_type_.__args__)
            if value not in options:
                value = options[0]
            options = kwargs.pop("options", options)
            kwargs = clean_kwargs(Select, kwargs)
            return Select(value=value, options=options, **kwargs)
        max_length = field.field_info.max_length
        min_length = field.field_info.min_length

    kwargs["min_length"] = min_length

    if max_length is None:
        kwargs = clean_kwargs(TextAreaInput, kwargs)
        return TextAreaInput(value=value, **kwargs)

    elif max_length < 100:
        kwargs = clean_kwargs(TextInput, kwargs)
        return TextInput(value=value, max_length=max_length, **kwargs)

    kwargs = clean_kwargs(TextAreaInput, kwargs)
    return TextAreaInput(value=value, max_length=max_length, **kwargs)


@dispatch
def infer_widget(value: List, field: Optional[ModelField] = None, **kwargs) -> Widget:
    if field is not None and type(field.type_) == _LiteralGenericAlias:
        options = list(field.type_.__args__)
        if value not in options:
            value = []
        kwargs = clean_kwargs(ListInput, kwargs)
        return MultiChoice(name=field.alias, 
                           value=value, options=options)

    kwargs = clean_kwargs(ListInput, kwargs)
    return ListInput(value=value, **kwargs)


@dispatch
def infer_widget(value: Dict, field: Optional[ModelField] = None, **kwargs) -> Widget:
    kwargs = clean_kwargs(DictInput, kwargs)
    return DictInput(value=value, **kwargs)


@dispatch
def infer_widget(value: tuple, field: Optional[ModelField] = None, **kwargs) -> Widget:
    kwargs = clean_kwargs(TupleInput, kwargs)
    return TupleInput(value=value, **kwargs)


@dispatch
def infer_widget(
    value: datetime.datetime, field: Optional[ModelField] = None, **kwargs
):
    kwargs = clean_kwargs(DatetimePicker, kwargs)
    return DatetimePicker(value=value, **kwargs)


@dispatch
def infer_widget(
    value: param.Parameterized, field: Optional[ModelField] = None, **kwargs
):
    kwargs = clean_kwargs(Param, kwargs)
    return Param(value, **kwargs)


@dispatch
def infer_widget(
    value: List[param.Parameterized], field: Optional[ModelField] = None, **kwargs
):
    kwargs = clean_kwargs(Param, kwargs)
    return Column(*[Param(val, **kwargs) for val in value])
