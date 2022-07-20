import param
import pydantic

from typing import Dict, List, Any, Type, ClassVar, Optional

from pydantic import ValidationError, BaseModel
from pydantic.fields import FieldInfo, ModelField
from pydantic.config import inherit_config

from plum import dispatch, NotFoundLookupError

import param

import panel as pn
from copy import copy

from panel.layout import Column, Divider, ListPanel, Card

from panel.widgets import Widget, CompositeWidget, Button, LiteralInput

from .dispatchers import json_serializable, get_widget, clean_kwargs


class Config:
    """Pydantic Config overrides for monkey patching
    synchronization into a model.
    """

    validate_assignment = True


class pydantic_widgets(param.ParameterizedFunction):
    """Returns a dictionary of widgets to edit the fields
    of a pydantic model.
    """

    model = param.ClassSelector(pydantic.BaseModel, is_instance=False)

    aliases = param.Dict({})

    widget_kwargs = param.Dict({})
    defaults = param.Dict({})
    use_model_aliases = param.Boolean(False)
    callback = param.Callable()

    def __call__(self, **params):

        p = param.ParamOverrides(self, params)

        if isinstance(p.model, BaseModel):
            self.defaults = {f: getattr(p.model, f, None) for f in p.model.__fields__}
            
        if p.use_model_aliases:
            default_aliases = {
                field.name: field.alias.capitalize()
                for field in p.model.__fields__.values()
            }
        else:
            default_aliases = {
                name: name.replace("_", " ").capitalize() for name in p.model.__fields__
            }

        aliases = params.get("aliases", default_aliases)

        widgets = {}
        for field_name, alias in aliases.items():
            field = p.model.__fields__[field_name]

            value = p.defaults.get(field_name, None)

            if value is None:
                value = field.default

            value = json_serializable(value)

            try:
                widget_builder = get_widget.invoke(field.outer_type_, field.__class__)
                widget = widget_builder(value, field, name=field_name, **p.widget_kwargs)

            except (NotFoundLookupError, NotImplementedError):
                widget = get_widget(value, field, name=field_name, **p.widget_kwargs)

            if p.callback is not None:
                widget.param.watch(p.callback, "value")
                
            widgets[field_name] = widget
        return widgets


class InstanceOverride:
    """This allows us to override pydantic class attributes
    for specific instance without touching the instance __dict__
    since pydantic expects the instance __dict__ to only hold field
    values. We implement the descriptor protocol and lookup the value
    based on the id of the instance.
    """

    @classmethod
    def override(cls, instance: Any, name: str, value: Any, default: Any = None):
        """Override the class attribute `name` with `value`
        only when accessed from `instance`.

        Args:
            instance (Any): An instance of some class
            name (str): the attribute to be overriden
            value (Any): the value to override with for this instance
            default (Any, optional): Default value to return for other instances.
                                     Only used if attribute doesnt exist on class.
                                     Defaults to None.

        Returns:
            Any: the instance that was passed
        """

        class_ = type(instance)

        if not hasattr(class_, name):
            setattr(class_, name, cls(default))

        elif not isinstance(vars(class_)[name], cls):
            setattr(class_, name, cls(getattr(class_, name)))

        vars(class_)[name].mapper[id(instance)] = value

        return instance

    def revert_override(self, instance: Any):
        return self.mapper.pop(id(instance))

    def __init__(self, default, mapper=None):
        self.default = default
        self.mapper = mapper or {}

    def __get__(self, obj, objtype=None):
        if id(obj) in self.mapper:
            return self.mapper[id(obj)]
        else:
            return self.default


class PydanticModelEditor(CompositeWidget):
    """A composet widget whos value is a pydantic model and whos
    children widgets are synced with the model attributes

    """

    _composite_type: ClassVar[Type[ListPanel]] = Column
    _trigger_recreate: ClassVar[List] = ["class_"]
    
    _widgets = param.Dict(default={}, constant=True)

    _updating = param.Boolean(False)
    _updating_field = param.Boolean(False)

    class_ = param.ClassSelector(
        class_=BaseModel, default=None, is_instance=False
    )

    fields = param.List([])

    by_alias = param.Boolean(False)

    bidirectional = param.Boolean(False)

    value = param.ClassSelector(class_=(BaseModel, dict))

    def __init__(self, **params):
        
        super().__init__(**params)
        self._recreate_widgets()
        self.param.watch(self._recreate_widgets, 
                         self._trigger_recreate)

        self.param.watch(self._update_value, "value")

        if self.value is not None:
            self.param.trigger("value")

        for w in self.widgets:
            w.param.trigger("value")


    @property
    def widgets(self):
        fields = self.fields if self.fields else list(self._widgets)
        return [self._widgets[field] for field in fields]

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
            for k,v in self.items():
                if k in self._widgets:
                    self._widgets[k].value = json_serializable(v)
                else:
                    self._recreate_widgets()
                    self.param.trigger('value')
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
            if not self.value.__config__.validate_assignment:
                config = inherit_config(Config, self.value.__config__)
                InstanceOverride.override(self.value, "__config__", config)

            # Add a callback to the root validators
            # to sync widgets to the changes made to
            # the model attributes
            callback = (False, self._update_widgets)
            if callback not in self.value.__post_root_validators__:
                validators = self.value.__post_root_validators__ + [callback]
                InstanceOverride.override(
                    self.value, "__post_root_validators__", validators
                )

            # If the previous value was a model
            # instance we unlink it by removing
            # the instance root validator and config
            if id(self.value) != id(event.old) and isinstance(event.old, BaseModel):
                for var in vars(type(event.old)).values():
                    if not isinstance(var, InstanceOverride):
                        continue
                    var.revert_override(event.old)

    def items(self):
        if self.value is None:
            return []
        return [(name, getattr(self.value, name)) 
                    for name in self.value.__fields__]

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

        for name, widget in self._widgets.items():
            if event.obj == widget:
                break
        else:
            return

        field = self.value.__fields__[name]
        data = {k: w.value for k, w in self._widgets.items()}

        val = data.pop(name, None)
        val, error = field.validate(val, data, loc=name)
        if error:
            self.updating = True
            try:
                event.obj.value = event.old
            finally:
                self.updating = False
            raise ValidationError([error], type(self.value))

        if self.value is not None:
            setattr(self.value, name, val)
            self._updating_field = True
            try:
                self.param.trigger("value")
            finally:
                self._updating_field = False

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
                val = json_serializable(values[k])
                if w.value != val:
                    w.value = val
        finally:
            self._updating = False

        return values

    @pn.depends("value")
    def json(self):
        if self.value is None:
            return pn.pane.JSON(width=self.width, sizing_mode="stretch_both")

        return pn.pane.JSON(
            object=self.value.json(), width=self.width, sizing_mode="stretch_both"
        )


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

import param

from pydantic_panel import get_widget

from typing import ClassVar, Type, List, Dict, Tuple, Any

import panel as pn
from panel.layout import Column, Divider, ListPanel, Card, Panel, Row

from panel.widgets import Widget, CompositeWidget, Button, LiteralInput


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
    
    class_ = param.ClassSelector(object, is_instance=False)
    
    default_item = param.Parameter(default=None)
    
    value = param.Parameter(default=None)
    
    __abstract = True
    
    def __init__(self, **params):
        super().__init__(**params)
        self.param.watch(self._value_changed, 'value')
        self.param.trigger('value')
        
    def _panel_for(self, name, widget):
        panel = Card(widget, header=str(name), collapsed=not self.expand)
        
        if self.allow_remove:
            remove_button = Button(name='❌')
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
            widget.param.watch(cb, 'value')
            self._widgets[name] = widget
        
    def _update_panels(self, *events):
        panels = [self._panel_for(name, widget) 
                  for name, widget in self._widgets.items()]
        if self.name:
            panels.insert(0, pn.panel(f'## {self.name.capitalize()}'))
        panels.append(pn.panel(self._controls))
        panels.append(Divider())
        
        self._composite[:] = panels
        
    def _sync_widgets(self, *events):
        for name, item in self.items():
            widget = self._widgets.get(name, None)
            if widget is None:
                continue
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
        
    def items(self) -> List[Tuple[str,Any]]:
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
        
    def items(self) -> List[Tuple[str,Any]]:
        return list(enumerate(self.value))
    
    def add_item(self, item, name=None):
        if name is None:
            name = len(self.value)
        idx = int(name)
        self.value.insert(idx, item)
        self.param.trigger('value')
        self.item_added = True
    
    def remove_item(self, name):
        self.value.pop(int(name))
        self.param.trigger('value')
        self.item_removed = True
    
    def sync_item(self, name):
        idx = int(name)
        self.value[idx] = self._widgets[idx].value
        self.param.trigger('value')
        
    def _add_new_cb(self, event):
        self.add_item(self.default_value)
    
    @param.depends('class_', 'allow_add')
    def _controls(self):
        if self.allow_add and self.class_ is not None:
            editor = self._widget_for(len(self.value), self.default_item)
            
            def cb(event):
                self.add_item(editor.value)
                
            add_button = Button(name='✅ Accept')
            add_button.on_click(cb)
            
            return Card(editor, add_button, header='➕ New', collapsed=True)
        
        return pn.Column()
    
    def _widget_for(self, name, item):
        if item is None:
            return get_widget.invoke(self.class_, None)(self.default_item, None, class_=self.class_, name=str(name))
        return get_widget(item, None, name=str(name))
    
    def _sync_values(self, *events):
        with param.parameterized.discard_events(self):
            self.value = [self._widgets[name].value for name in self.keys()]
        

class ItemDictEditor(BaseCollectionEditor):
    value = param.Dict(default={}, )
    
    key_type = param.ClassSelector(object, default=str, is_instance=False)
    
    default_key = param.Parameter(default='')
    
    def keys(self):
        return list(self.value)
        
    def values(self):
        return list(self.value.values())
        
    def items(self) -> List[Tuple[str,Any]]:
        return list(self.value.items())
    
    def add_item(self, item, name=None):
        if name is None:
            name = self.default_key
        self.value[name] = item
        self.param.trigger('value')
        self.item_added = True
                
    def remove_item(self, name):
        self.value.pop(name, None)
        self.param.trigger('value')
        self.item_removed = True
    
    def sync_item(self, name):
        self.value[name] = self._widgets[name].value
        self.param.trigger('value')
        
    def _widget_for(self, name, item):
        if item is None:
            return get_widget.invoke(self.class_, None)(item, None, class_=self.class_, name=str(name))
        return get_widget(item, None, name=str(name))
    
    def _sync_values(self, *events):
        with param.parameterized.discard_events(self):
            self.value = {name: self._widgets[name].value for name in self.keys()}
    

    @param.depends('class_', 'allow_add')
    def _controls(self):
        if self.allow_add and self.class_ is not None:
            key_editor = get_widget(self.default_key, None, name='Key', max_length=50)
            editor = self._widget_for(self.default_key, self.default_item)
            editor.name = 'Value'
            
            def cb(event):
                self.add_item(editor.value, key_editor.value)
                
            add_button = Button(name='✅ Accept')
            add_button.on_click(cb)
            
            return Card(key_editor, editor, add_button, header='➕ New', collapsed=True)
        return pn.Column()


@dispatch
def get_widget(value: BaseModel, field: Any, **kwargs):
    if field is None:
        class_= kwargs.pop('class_', type(value))
        return PydanticModelEditor(value=value, class_=class_, **kwargs)

    class_ = kwargs.pop('class_', field.outer_type_)
    kwargs = clean_kwargs(PydanticModelEditorCard, kwargs)
    return PydanticModelEditorCard(value=value, class_=class_, **kwargs)


@dispatch
def get_widget(value: List[BaseModel], field: Any, **kwargs):
    

    if field is not None:
        kwargs['class_'] = kwargs.pop('class_', field.type_)
        if value is None:
            value = field.default
    
    if value is None:
        value = []
    kwargs = clean_kwargs(ItemListEditor, kwargs)
    return ItemListEditor(value=value, **kwargs)

@dispatch
def get_widget(value: Dict[str,BaseModel], field: Any, **kwargs):
    
    if field is not None:
        kwargs['class_'] = kwargs.pop('class_', field.type_)
        if value is None:
            value = field.default
            
    if value is None:
        value = {}
 
    kwargs['key_type'] = kwargs.pop('key_type', str)
    kwargs = clean_kwargs(ItemDictEditor, kwargs)
    return ItemDictEditor(value=value, **kwargs)



