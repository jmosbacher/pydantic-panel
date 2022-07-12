import datetime
from typing import Dict, List, Any

try:
    from typing import _LiteralGenericAlias
except ImportError:
    _LiteralGenericAlias = None

from plum import dispatch
from numbers import Integral, Number


from panel.widgets import (
    LiteralInput,
    IntInput,
    NumberInput,
    DatetimePicker,
    Checkbox,
    TextInput,
    TextAreaInput,
    ArrayInput,
    Select,
)


ListInput = type("ListInput", (LiteralInput,), {"type": list})
DictInput = type("DictInput", (LiteralInput,), {"type": dict})
TupleInput = type("TupleInput", (LiteralInput,), {"type": tuple})


@dispatch
def get_widget(value: Any, field: Any, **kwargs):
    '''Fallback function when a more specific
    function was not registered.
    '''
    if type(field.outer_type_) == _LiteralGenericAlias:
        options = list(field.outer_type_.__args__)
        if value not in options:
            values = options[0]
        return Select(value=value, options=options, **kwargs)

    return LiteralInput(value=value, **kwargs)


@dispatch
def get_widget(value: Integral, field: Any, **kwargs):
    if type(field.outer_type_) == _LiteralGenericAlias:
        options = list(field.outer_type_.__args__)
        if value not in options:
            values = options[0]
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

    return IntInput(value=value, start=start, end=end, **kwargs)


@dispatch
def get_widget(value: Number, field: Any, **kwargs):
    if type(field.outer_type_) == _LiteralGenericAlias:
        options = list(field.outer_type_.__args__)
        if value not in options:
            values = options[0]
        return Select(value=value, options=options, **kwargs)

    start = getattr(field.field_info, "gt", None)
    end = getattr(field.field_info, "lt", None)
    return NumberInput(value=value, start=start, end=end, **kwargs)


@dispatch
def get_widget(value: bool, field: Any, **kwargs):
    if value is None:
        value = False
    return Checkbox(value=value, **kwargs)


@dispatch
def get_widget(value: str, field: Any, **kwargs):
    if type(field.outer_type_) == _LiteralGenericAlias:
        options = list(field.outer_type_.__args__)
        if value not in options:
            values = options[0]
        return Select(value=value, options=options, **kwargs)
    max_len = field.field_info.max_length

    if max_len is None:
        return TextAreaInput(value=value, **kwargs)

    elif max_len < 100:
        return TextInput(value=value, max_length=max_len, **kwargs)

    return TextAreaInput(value=value, max_length=max_len, **kwargs)


@dispatch
def get_widget(value: List, field: Any, **kwargs):
    return ListInput(value=value, **kwargs)


@dispatch
def get_widget(value: Dict, field: Any, **kwargs):
    return DictInput(value=value, **kwargs)


@dispatch
def get_widget(value: tuple, field: Any, **kwargs):
    return TupleInput(value=value, **kwargs)


@dispatch
def get_widget(value: datetime.datetime, field: Any, **kwargs):
    start = getattr(field.field_info, "gt", None)
    end = getattr(field.field_info, "lt", None)
    return DatetimePicker(value=value, start=start, end=end, **kwargs)


try:
    import numpy

    @dispatch
    def get_widget(value: numpy.ndarray, field: Any, **kwargs):
        return ArrayInput(value=value, **kwargs)

except ImportError:
    pass


@dispatch
def json_serializable(value: Any):
    return value


@dispatch
def json_serializable(value: list):
    return [json_serializable(v) for v in value]


@dispatch
def json_serializable(value: tuple):
    return tuple(json_serializable(v) for v in value)


@dispatch
def json_serializable(value: dict):
    return {json_serializable(k): json_serializable(v) for k, v in value.items()}


try:
    import pandas

    @dispatch
    def json_serializable(value: pandas.Interval):
        return (value.left, value.right)

except ImportError:
    pass
