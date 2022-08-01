
import numpy as np

from typing import Optional
from plum import dispatch, parametric, type_of
from pydantic.fields import ModelField
from panel.widgets import Widget, ArrayInput

from .dispatchers import clean_kwargs


@dispatch
def infer_widget(
    value: np.ndarray, field: Optional[ModelField] = None, **kwargs
) -> Widget:
    kwargs = clean_kwargs(ArrayInput, kwargs)
    return ArrayInput(value=value, **kwargs)


# Taken from plum examples
# This is mostly for users to be able to define custom widgets based
# on the shape of the array. For now we dispatch all numpy arrays to the
# same widget constructor.
@parametric(runtime_type_of=True)
class NPArray(np.ndarray):
    """A type for NumPy arrays where the type parameter specifies the number of
    dimensions.
    """


@type_of.dispatch
def type_of(x: np.ndarray):
    '''Hook into Plum's type inference system to produce
     an appropriate instance of `NPArray` for NumPy arrays.
    '''
    return NPArray[x.ndim]

