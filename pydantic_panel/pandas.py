from typing import Optional
from plum import dispatch

import param
import pandas as pd

from pydantic.fields import ModelField
from panel.widgets import DatetimeRangePicker, EditableRangeSlider

from .dispatchers import clean_kwargs


class PandasTimeIntervalEditor(DatetimeRangePicker):
    value = param.ClassSelector(pd.Interval, default=None)

    def _serialize_value(self, value):
        value = super()._serialize_value(value)
        if any([v is None for v in value]):
            return None
        left = pd.Timestamp(value[0])
        right = pd.Timestamp(value[1])
        return pd.Interval(left, right)

    def _deserialize_value(self, value):
        if isinstance(value, pd.Interval):
            value = (value.left.to_pydatetime(), value.right.to_pydatetime())

        value = super()._deserialize_value(value)
        return value

    @param.depends("start", "end", watch=True)
    def _update_value_bounds(self):
        pass


class PandasIntervalEditor(EditableRangeSlider):

    value = param.ClassSelector(pd.Interval, default=None)

    value_throttled = param.ClassSelector(pd.Interval, default=None)

    @param.depends("value", watch=True)
    def _update_value(self):
        if self.value is None:
            return

        self._slider.value = (self.value.left, self.value.right)
        self._start_edit.value = self.value.left
        self._end_edit.value = self.value.right

    def _sync_value(self, event):
        with param.edit_constant(self):
            new_value = pd.Interval(left=event.new[0], right=event.new[1])
            self.param.update(**{event.name: new_value})

    def _sync_start_value(self, event):
        if event.name == "value":
            end = self.value.right if self.value else self.end
        else:
            end = self.value_throttled.right if self.value_throttled else self.end

        new_value = pd.Interval(left=event.new, right=end)

        with param.edit_constant(self):
            self.param.update(**{event.name: new_value})

    def _sync_end_value(self, event):
        if event.name == "value":
            start = self.value.left if self.value else self.start
        else:
            start = self.value_throttled.left if self.value_throttled else self.start

        new_value = pd.Interval(left=start, right=event.new)
        with param.edit_constant(self):
            self.param.update(**{event.name: new_value})


class PandasIntegerIntervalEditor(PandasIntervalEditor):

    step = param.Integer(default=1, constant=True)

    format = param.String(default="0", constant=True)


@dispatch
def infer_widget(value: pd.Interval, field: Optional[ModelField] = None, **kwargs):
    if isinstance(value.left, pd.Timestamp) or isinstance(value.right, pd.Timestamp):
        kwargs = clean_kwargs(PandasTimeIntervalEditor, kwargs)
        return PandasTimeIntervalEditor(value=value, **kwargs)

    start = None
    end = None
    step = None
    if field is not None:
        start = field.field_info.ge or field.field_info.gt
        end = field.field_info.le or field.field_info.lt
        step = field.field_info.multiple_of

    if start is None:
        start = kwargs.get("start", 0)

    if end is None:
        end = kwargs.get("end", 1)

    if isinstance(value.left, int) or isinstance(value.right, int):

        if step is None:
            step = kwargs.get("step", 1)

        kwargs = clean_kwargs(PandasIntegerIntervalEditor, kwargs)
        return PandasIntegerIntervalEditor(
            value=value, step=step, start=start, end=end, **kwargs
        )

    if step is None:
        step = kwargs.get("step", 0.001)

    kwargs = clean_kwargs(PandasIntervalEditor, kwargs)
    return PandasIntervalEditor(value=value, step=step, start=start, end=end, **kwargs)
