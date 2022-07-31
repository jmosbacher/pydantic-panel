from __future__ import annotations

import param
import pydantic
from bokeh.document import Document
from bokeh.model import Model
from panel.io import init_doc, state
from panel.layout import Panel, WidgetBox
from panel.pane import PaneBase
from pyviz_comms import Comm


from typing import (
    Any,
    ClassVar,
    Optional,
)

from .dispatchers import infer_widget

pyobject = object


class Pydantic(PaneBase):
    """The Pydantic pane wraps your Pydantic model into a Panel component.

    You can use the component to edit your model or power your data app.

    Example:

    >>> from pydantic_panel import Pydantic
    >>> widget = Pydantic(SomePydanticModel)

    or alternatively

    >>> import pydantic_panel
    >>> widget = pn.panel(SomePydanticModel)

    Args:
        object (BaseModel): A Pydantic model
        default_layout (Panel): A WidgetBox, Row, Column or other Panel to
            layout the widgets.

    In addition you can use all the usual styling related arguments like
    height, width, sizing_mode etc.
    """

    priority: ClassVar = None

    default_layout: Panel = param.ClassSelector(
        default=WidgetBox, class_=Panel, is_instance=False
    )

    object = param.Parameter(default=None)

    def __init__(self, object=None, default_layout: Panel | None = None, **params):
        if default_layout:
            params["default_layout"] = default_layout

        pane_params = {
            name: params[name] for name in Pydantic.param.params() if name in params
        }

        super().__init__(object, **pane_params)

        if isinstance(object, type):

            if issubclass(object, pydantic.BaseModel):
                params["class_"] = object

            self.widget = infer_widget.invoke(object)(None, **params)
            self.widget.link(self, value="object")

        elif isinstance(object, pyobject):
            self.widget = infer_widget(object, **params)
            self.object = object

        else:
            raise

        self.layout = self.default_layout(self.widget)

    def _get_model(
        self,
        doc: Document,
        root: Optional[Model] = None,
        parent: Optional[Model] = None,
        comm: Optional[Comm] = None,
    ) -> Model:
        model = self.layout._get_model(doc, root, parent, comm)
        self._models[root.ref["id"]] = (model, parent)
        return model

    def _cleanup(self, root: Optional[Model] = None) -> None:
        self.layout._cleanup(root)
        super()._cleanup(root)

    @classmethod
    def applies(cls, obj: Any, **params) -> Optional[bool]:
        if isinstance(obj, param.Parameterized):
            return False

        if isinstance(obj, object):
            if isinstance(obj, pydantic.BaseModel):
                return 1
            elif isinstance(obj, list) and all(
                isinstance(o, pydantic.BaseModel) for o in obj
            ):
                return 1
            elif isinstance(obj, dict) and all(
                isinstance(o, pydantic.BaseModel) for o in obj.values()
            ):
                return 1
            try:
                infer_widget(obj)
                return 0.01
            except:
                pass

        if isinstance(obj, type):
            if issubclass(obj, pydantic.BaseModel):
                return 1
            try:
                infer_widget.invoke(obj)
                return 0.01
            except:
                pass

        return False

    def select(self, selector=None):
        """
        Iterates over the Viewable and any potential children in the
        applying the Selector.

        Arguments
        ---------
        selector: type or callable or None
          The selector allows selecting a subset of Viewables by
          declaring a type or callable function to filter by.

        Returns
        -------
        viewables: list(Viewable)
        """
        return super().select(selector) + self.layout.select(selector)

    def get_root(
        self,
        doc: Optional[Document] = None,
        comm: Optional[Comm] = None,
        preprocess: bool = True,
    ) -> Model:
        """
        Returns the root model and applies pre-processing hooks

        Arguments
        ---------
        doc: bokeh.Document
          Bokeh document the bokeh model will be attached to.
        comm: pyviz_comms.Comm
          Optional pyviz_comms when working in notebook
        preprocess: boolean (default=True)
          Whether to run preprocessing hooks

        Returns
        -------
        Returns the bokeh model corresponding to this panel object
        """
        doc = init_doc(doc)
        root = self.layout.get_root(doc, comm, preprocess)
        ref = root.ref["id"]
        self._models[ref] = (root, None)
        state._views[ref] = (self, root, doc, comm)
        return root
