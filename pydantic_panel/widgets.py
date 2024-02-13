from ast import Import
import param
import pydantic

from typing import Dict, List, Any, Optional, Type, ClassVar

from pydantic import ValidationError, BaseModel
from pydantic.fields import FieldInfo

from plum import dispatch, NotFoundLookupError

import param

import panel as pn

from panel.layout import Column, Divider, ListPanel, Card

from panel.widgets import CompositeWidget, Button

from .dispatchers import infer_widget, clean_kwargs

from pydantic_panel import infer_widget
from typing import ClassVar, Type, List, Dict, Tuple, Any

# See https://github.com/holoviz/panel/issues/3736
JSON_HACK_MARGIN = (10, 10)


def get_theme():
    return pn.state.session_args.get("theme", [b"default"])[0].decode()


def get_json_theme():
    if get_theme() == "dark":
        return "dark"
    return "light"


class Config:
    """Pydantic Config overrides for monkey patching
    synchronization into a model.
    """

    validate_assignment = True


class pydantic_widgets(param.ParameterizedFunction):
    """Returns a dictionary of widgets to edit the fields
    of a pydantic model.
    """

    model = param.ClassSelector(class_=pydantic.BaseModel, is_instance=False)

    aliases = param.Dict({})

    widget_kwargs = param.Dict({})
    defaults = param.Dict({})
    use_model_aliases = param.Boolean(False)
    callback = param.Callable()

    def __call__(self, **params):

        p = param.ParamOverrides(self, params)

        if isinstance(p.model, BaseModel):
            self.defaults = {f: getattr(p.model, f, None) for f in p.model.model_fields}

        if p.use_model_aliases:
            default_aliases = {
                field.name: field.alias.capitalize()
                for field in p.model.model_fields.values()
            }
        else:
            default_aliases = {
                name: name.replace("_", " ").capitalize() for name in p.model.model_fields
            }

        aliases = params.get("aliases", default_aliases)

        widgets = {}
        for field_name, alias in aliases.items():
            field = p.model.model_fields[field_name]

            value = p.defaults.get(field_name, None)

            if value is None:
                value = field.default

            try:
                widget_builder = infer_widget.invoke(field.annotation, field.__class__)
                widget = widget_builder(
                    value, field, name=field_name, **p.widget_kwargs
                )

            except (NotFoundLookupError, NotImplementedError):
                widget = infer_widget(value, field, name=field_name, **p.widget_kwargs)

            if p.callback is not None:
                widget.param.watch(p.callback, "value")

            widgets[field_name] = widget
        return widgets


class PydanticModelEditor(CompositeWidget):
    """A composet widget whos value is a pydantic model and whos
    children widgets are synced with the model attributes

    """

    _composite_type: ClassVar[Type[ListPanel]] = Column
    _trigger_recreate: ClassVar[List] = ["class_"]

    _widgets = param.Dict(default={}, constant=True)

    _updating = param.Boolean(False)
    _updating_field = param.Boolean(False)

    class_ = param.ClassSelector(class_=BaseModel, default=None, is_instance=False)

    fields = param.List([])

    by_alias = param.Boolean(False)

    bidirectional = param.Boolean(False)

    value = param.ClassSelector(class_=(BaseModel, dict))

    def __init__(self, **params):

        super().__init__(**params)
        self._recreate_widgets()
        self.param.watch(self._recreate_widgets, self._trigger_recreate)

        self.param.watch(self._update_value, "value")

        if self.value is not None:
            self.param.trigger("value")

        for w in self.widgets:
            w.param.trigger("value")

    @property
    def widgets(self):
        fields = self.fields if self.fields else list(self._widgets)
        return [self._widgets[field] for field in fields if field in self._widgets]
    
    def _recreate_widgets(self, *events):
        if self.class_ is None:
            self.value = None
            return

        widgets = pydantic_widgets(
            model=self.class_,
            defaults=dict(self.items()),
            callback=self._validate_field,
            use_model_aliases=self.by_alias,
            widget_kwargs=dict(bidirectional=self.bidirectional),
        )

        with param.edit_constant(self):
            self._widgets = widgets

        self._composite[:] = self.widgets

    def _update_value(self, event: param.Event):

        if self._updating_field:
            return

        if self.value is None:
            for widget in self.widgets:
                try:
                    widget.value = None
                except:
                    pass
            return

        if self.class_ is None and isinstance(self.value, BaseModel):
            self.class_ = type(self.value)

        if isinstance(self.value, self.class_):
            for k, v in self.items():
                if k in self._widgets:
                    self._widgets[k].value = v
                else:
                    self._recreate_widgets()
                    self.param.trigger("value")
                    return

        elif isinstance(self.value, dict) and not set(self.value).symmetric_difference(
            self._widgets
        ):
            self.value = self.class_(**self.value)
            return
        else:
            raise ValueError(
                f"value must be an instance of {self._class}"
                " or a dict matching its fields."
            )

        # HACK for biderectional sync
        if self.value is not None and self.bidirectional:

            # We need to ensure the model validates on assignment
            if not self.value.model_config.get("validate_assignment", False):
                config = self.value.model_config.copy()
                config.update(validate_assignment=True)

            # Add a callback to the root validators
            # sync widgets to the changes made directly
            # to the model attributes
            add_setattr_callback(self.value, self._update_widget)


            # If the previous value was a model
            # instance we unlink it
            if id(self.value) != id(event.old) and isinstance(event.old, BaseModel):
                remove_setattr_callback(event.old, self._update_widget)

    def __del__(self):
        if self.value is not None and self.bidirectional:
            remove_setattr_callback(self.value, self._update_widget)

    def items(self):
        if self.value is None:
            return []
        return [(name, getattr(self.value, name)) 
                for name in self.value.model_fields]

    def _validate_field(self, event: param.Event):
        if not event or self._updating:
            return

        if self.value is None:
            if self.class_ is not None:
                try:
                    data = {k: w.value for k, w in self._widgets.items()}
                    self.value = self.class_(**data)
                except:
                    pass
            return

        if self.value is None:
            return
        
        for name, widget in self._widgets.items():
            if event.obj == widget:
                break
        else:
            return

        try:
            self.class_.__pydantic_validator__.validate_assignment(self.value, 
                                                                   name, 
                                                                   event.new)
        except ValidationError as e:
            self._updating = True
            try:
                event.obj.value = event.old
                self._updating_field = True
                self.param.trigger("value")
                self._updating_field = False
            finally:
                self._updating = False
            raise e

    def _update_widget(self, name, value):
        if self._updating:
            return

        if name in self._widgets:
            self._updating = True
            try:
                self._widgets[name].value = value
            finally:
                self._updating = False

    def _update_widgets(self, cls, values):
        if self.value is None:
            return

        if self._updating:
            return values

        self._updating = True
        try:
            for k, w in self._widgets.items():
                if k not in values:
                    continue
                val = values[k]
                if w.value != val:
                    w.value = val
        finally:
            self._updating = False

        return values

    @pn.depends("value")
    def json(self):
        if self.value is None:
            return pn.pane.JSON(
                width=self.width,
                sizing_mode="stretch_both",
                theme=get_json_theme(),
                margin=JSON_HACK_MARGIN,
            )

        return pn.pane.JSON(
            object=self.value.json(),
            width=self.width,
            sizing_mode="stretch_both",
            theme=get_json_theme(),
            margin=JSON_HACK_MARGIN,
        )


def add_setattr_callback(model_instance: BaseModel, callback: callable):
    """Syncs the fields of a pydantic model with a dictionary of widgets

    Args:
        model_instance (BaseModel): The model instance to sync
        callback (callable): The callback function to sync the fields

    Returns:
        callback: A callback function that can be used to unsync the fields
    """

    class_ = model_instance.__class__
    if hasattr(class_, "__panel_callbacks__"):
        class_.__panel_callbacks__ += (callback,)
    else:
        class ModifiedModel(class_):
            __panel_callbacks__ = (callback,)

            def __setattr__(self, name, value):
                super().__setattr__(name, value)
                if not hasattr(self.__class__, "__panel_callbacks__"):
                    return
                for cb in self.__class__.__panel_callbacks__:
                    cb(name, value)
    
    model_instance.__class__ = ModifiedModel

    return callback

def remove_setattr_callback(model_instance: BaseModel, callback: callable):
    """Unsyncs the fields of a pydantic model with a dictionary of widgets

    Args:
        model_instance (BaseModel): The model instance to unsync

    Returns:
        None
    """
    class_ = model_instance.__class__

    if hasattr(class_, "__panel_callbacks__"):
            class_.__panel_callbacks__ = tuple(
                cb for cb in class_.__panel_callbacks__ if cb is not callback
            )
    else:
        return
    
    if class_.__panel_callbacks__:
        return
    
    for class_ in model_instance.__class__.mro():
        if hasattr(class_, "__panel_callbacks__"):
            continue
        model_instance.__class__ = class_


class PydanticModelEditorCard(PydanticModelEditor):
    """Same as PydanticModelEditor but uses a Card container
    to hold the widgets and synces the header with the widget `name`
    """

    _composite_type: ClassVar[Type[ListPanel]] = Card
    collapsed = param.Boolean(False)

    def __init__(self, **params):
        super().__init__(**params)
        self._composite.header = self.name
        self.link(self._composite, name="header")
        self.link(self._composite, collapsed="collapsed")


class BaseCollectionEditor(CompositeWidget):
    """Composite widget for editing a collections of items"""

    _composite_type: ClassVar[Type[ListPanel]] = Column

    _new_editor = param.Parameter()

    _widgets = param.Dict({})

    allow_add = param.Boolean(True)
    allow_remove = param.Boolean(True)

    item_added = param.Event()
    item_removed = param.Event()

    expand = param.Boolean(True)

    class_ = param.ClassSelector(class_=object, is_instance=False)

    item_field = param.ClassSelector(class_=FieldInfo, default=None, allow_None=True)

    default_item = param.Parameter(default=None)

    value = param.Parameter(default=None)

    __abstract = True

    def __init__(self, **params):
        super().__init__(**params)
        self.param.watch(self._value_changed, "value")
        self.param.trigger("value")

    def _panel_for(self, name, widget):
        if isinstance(widget, CompositeWidget):
            panel = Card(widget, header=str(name), collapsed=not self.expand)
        else:
            widget.width = 200
            panel = pn.Row(widget)

        if self.allow_remove:
            remove_button = Button(name="❌", width=50, width_policy="auto", align="end")

            def cb(event):
                self.remove_item(name)

            remove_button.on_click(cb)
            panel.append(remove_button)
        return panel

    def _create_widgets(self, *events, reset=True):
        if reset:
            self._widgets = {}
        for name, item in self.items():
            widget = self._widget_for(name, item)

            def cb(event):
                self.sync_item(name)

            widget.param.watch(cb, "value")
            self._widgets[name] = widget

    def _update_panels(self, *events):
        panels = [
            self._panel_for(name, widget) for name, widget in self._widgets.items()
        ]
        if self.name:
            panels.insert(0, pn.panel(f"### {self.name.capitalize()}"))
        panels.append(pn.panel(self._controls))
        panels.append(Divider())

        self._composite[:] = panels

    def _sync_widgets(self, *events):
        for name, item in self.items():
            widget = self._widgets.get(name, None)
            if widget is None:
                continue
            with param.parameterized.discard_events(widget):
                widget.value = item

    def _value_changed(self, *event):
        if not self.value:
            self._widgets = {}
            self._update_panels()
            return
        if set(self._widgets).symmetric_difference(self.keys()):
            self._create_widgets()
            self._update_panels()
        else:
            self._sync_widgets()

    def _controls(self):
        return pn.Column()

    def keys(self):
        raise NotImplementedError

    def values(self):
        raise NotImplementedError

    def items(self) -> list[Tuple[str, Any]]:
        raise NotImplementedError

    def add_item(self, item, name=None):
        raise NotImplementedError

    def remove_item(self, name):
        raise NotImplementedError

    def sync_item(self, name):
        raise NotImplementedError

    def _widget_for(self, name, item):
        raise NotImplementedError

    def _sync_values(self, *events):
        raise NotImplementedError


class ItemListEditor(BaseCollectionEditor):

    value = param.List(default=[])

    def keys(self):
        return list(range(len(self.value)))

    def values(self):
        return list(self.value)

    def items(self) -> list[Tuple[str, Any]]:
        return list(enumerate(self.value))

    def add_item(self, item, name=None):
        if name is None:
            name = len(self.value)
        idx = int(name)
        self.value.insert(idx, item)
        self.param.trigger("value")
        self.item_added = True

    def remove_item(self, name):
        self.value.pop(int(name))
        self.param.trigger("value")
        self.item_removed = True

    def sync_item(self, name):
        idx = int(name)
        self.value[idx] = self._widgets[idx].value
        self.param.trigger("value")

    def _add_new_cb(self, event):
        self.add_item(self.default_value)

    @param.depends("class_", "allow_add")
    def _controls(self):
        if self.allow_add and self.class_ is not None:
            editor = self._widget_for(len(self.value), self.default_item)

            def cb(event):
                if editor.value is not None:
                    self.add_item(editor.value)

            if isinstance(editor, CompositeWidget):
                add_button = Button(name="✅ Insert")
                add_button.on_click(cb)
                return Card(
                    editor,
                    add_button,
                    header="➕ Add",
                    collapsed=True,
                    width_policy="min",
                )
            else:
                add_button = Button(
                    name="➕", width=50, width_policy="auto", align="end"
                )
                add_button.on_click(cb)
                editor.width = 200
                return pn.Row(editor, add_button)
        return pn.Column()

    def _widget_for(self, name, item):
        if item is None:
            return infer_widget.invoke(self.class_, None)(
                self.default_item, self.item_field, class_=self.class_, name=str(name)
            )
        return infer_widget(item, self.item_field, name=str(name))

    def _sync_values(self, *events):
        with param.parameterized.discard_events(self):
            self.value = [self._widgets[name].value for name in self.keys()]


class ItemDictEditor(BaseCollectionEditor):
    value = param.Dict(
        default={},
    )

    key_type = param.ClassSelector(class_=object, default=str, is_instance=False)

    default_key = param.Parameter(default="")

    def keys(self):
        return list(self.value)

    def values(self):
        return list(self.value.values())

    def items(self) -> list[tuple[str, Any]]:
        return list(self.value.items())

    def add_item(self, item, name=None):
        if name is None:
            name = self.default_key
        self.value[name] = item
        self.param.trigger("value")
        self.item_added = True

    def remove_item(self, name):
        self.value.pop(name, None)
        self.param.trigger("value")
        self.item_removed = True

    def sync_item(self, name):
        self.value[name] = self._widgets[name].value
        self.param.trigger("value")

    def _widget_for(self, name, item):
        if item is None:
            return infer_widget.invoke(self.class_, self.item_field)(
                item, self.item_field, class_=self.class_, name=str(name)
            )

        return infer_widget(item, self.item_field, name=str(name))

    def _sync_values(self, *events):
        with param.parameterized.discard_events(self):
            self.value = {name: self._widgets[name].value for name in self.keys()}

    @param.depends("class_", "allow_add")
    def _controls(self):
        if self.allow_add and self.class_ is not None:
            key_editor = infer_widget(self.default_key, None, name="Key", max_length=50)
            editor = self._widget_for(self.default_key, self.default_item)
            editor.name = "Value"

            def cb(event):
                if editor.value is None:
                    self.add_item(editor.value, key_editor.value)

            add_button = Button(name="✅ Insert")
            add_button.on_click(cb)

            return Card(
                key_editor,
                editor,
                add_button,
                header="➕ Add",
                collapsed=True,
                width_policy="min",
            )
        return pn.Column()


@dispatch
def infer_widget(value: BaseModel, field: Optional[FieldInfo] = None, **kwargs):
    if field is None:
        class_ = kwargs.pop("class_", type(value))
        return PydanticModelEditor(value=value, class_=class_, **kwargs)

    class_ = kwargs.pop("class_", field.annotation)
    kwargs = clean_kwargs(PydanticModelEditorCard, kwargs)
    return PydanticModelEditorCard(value=value, class_=class_, **kwargs)


@dispatch
def infer_widget(value: list[BaseModel], field: Optional[FieldInfo] = None, **kwargs):

    if field is not None:
        kwargs["class_"] = kwargs.pop("class_", field.annotation)
        if value is None:
            value = field.default

    if value is None:
        value = []
    kwargs = clean_kwargs(ItemListEditor, kwargs)
    return ItemListEditor(value=value, **kwargs)


@dispatch
def infer_widget(
    value: dict[str, BaseModel], field: Optional[FieldInfo] = None, **kwargs
):

    if field is not None:
        kwargs["class_"] = kwargs.pop("class_", field.annotation)
        if value is None:
            value = field.default

    if value is None:
        value = {}

    kwargs["key_type"] = kwargs.pop("key_type", str)
    kwargs = clean_kwargs(ItemDictEditor, kwargs)
    return ItemDictEditor(value=value, **kwargs)
