import param
import pydantic

from typing import Dict, List, Any, Type, ClassVar, Optional

from pydantic import ValidationError, BaseModel
from pydantic.config import inherit_config

from plum import dispatch, NotFoundLookupError

import param

from panel.layout import Column, Divider, ListPanel, Card

from panel.widgets import CompositeWidget, Button

from .dispatchers import json_serializable, get_widget


class Config:
    '''Pydantic Config overrides for monkey patching
    synchronization into a model. 
    '''

    validate_assignment = True


class pydantic_widgets(param.ParameterizedFunction):
    ''' Returns a dictionary of widgets to edit the fields
    of a pydantic model.
    '''

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
                for name in p.model.__fields__.values()
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
                widget = widget_builder(value, field, name=alias, **p.widget_kwargs)

            except (NotFoundLookupError, NotImplementedError):
                widget = get_widget(value, field, name=alias, **p.widget_kwargs)

            if p.callback is not None:
                if hasattr(widget, "value_throttled"):
                    widget.param.watch(p.callback, "value")
                else:
                    widget.param.watch(p.callback, "value")

            widgets[field_name] = widget
        return widgets


class InstanceOverride:
    '''This allows us to override pydantic class attributes
    for specific instance without touching the instance __dict__
    since pydantic expects the instance __dict__ to only hold field
    values. We implement the descriptor protocol and lookup the value
    based on the id of the instance.
    '''
    

    @classmethod
    def override(cls, instance: Any, name: str, value: Any, default: Any =None):
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

    def __init__(self, default, mapper=None):
        self.default = default
        self.mapper = mapper or {}

    def __get__(self, obj, objtype=None):
        if id(obj) in self.mapper:
            return self.mapper[id(obj)]
        else:
            return self.default


class PydanticModelEditor(CompositeWidget):
    '''A composet widget whos value is a pydantic model and whos
     children widgets are synced with the model attributes
    
    '''
    _composite_type: ClassVar[Type[ListPanel]] = Column

    _widgets = param.Dict()

    _updating = param.Boolean(False)
    _updating_field = param.Boolean(False)

    extra_widgets = param.List([])

    class_ = param.ClassSelector(BaseModel, is_instance=False)

    fields = param.List()

    bidirectional = param.Boolean(False)

    value = param.ClassSelector(BaseModel)

    def __init__(self, **params):

        super().__init__(**params)
        self._update_value()
        self.param.watch(self._update_value, "value")

    @property
    def widgets(self):
        fields = self.fields if self.fields else list(self._widgets)
        return [self._widgets[field] for field in fields]

    def _update_value(self, event: param.Event = None):
        if self._updating_field:
            return

        value = event.new if event else self.value

        if value is None and self.class_ is not None:
            self._widgets = pydantic_widgets(
                model=self.class_, callback=self._validate_field
            )
            self._composite[:] = self.widgets + self.extra_widgets
            return

        if isinstance(value, BaseModel):
            self.class_ = type(value)
            self._widgets = pydantic_widgets(model=value, callback=self._validate_field)
            self._composite[:] = self.widgets + self.extra_widgets
            data = {}

        elif isinstance(value, dict):
            data = value

        else:
            raise ValueError

        for k, v in data.items():
            self._widgets[k].value = v

        # HACK for biderectional sync
        if value is not None and self.bidirectional:
            class_ = value.__class__
        
            # We need to ensure the model validates on assignment
            if not value.__config__.validate_assignment:
                config = inherit_config(Config, value.__config__)
                InstanceOverride.override(value, "__config__", config)

            # Add a callback to the root validators
            # to sync widgets to the changes made to
            # the model attributes
            callback = (False, self._update_widgets)
            if callback not in value.__post_root_validators__:
                validators = value.__post_root_validators__ + [callback]
                InstanceOverride.override(value, "__post_root_validators__", validators)

            # If the previous value was a model 
            # instance we unlink it by removing
            # the instance root validator and config
            if isinstance(event.old, BaseModel):
                for var in vars(type(event.old)).values():
                    if not isinstance(var, InstanceOverride):
                        continue
                    var.mapper.pop(id(event.old), None)

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
            event.obj.value = event.old
            raise ValidationError([error], type(self.value))

        if self.value is not None:
            setattr(self.value, name, val)
            self._updating_field = True
            try:
                self.param.trigger('value')
            finally:
                self._updating_field =  False

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


class PydanticModelEditorCard(PydanticModelEditor):
    '''Same as PydanticModelEditor but uses a Card container
    to hold the widgets and synces the header with the widget `name`
    '''
    _composite_type: ClassVar[Type[ListPanel]] = Card

    def __init__(self, **params):
        super().__init__(**params)
        self._composite.header = self.name
        self.link(self._composite, name="header")


class PydanticModelListEditor(CompositeWidget):
    ''' Composite widget for editing a list of pydantic models
    '''
    _composite_type: ClassVar[Type[ListPanel]] = Column

    _updating_item = param.Boolean(False)

    _new_editor = param.Parameter()

    class_ = param.ClassSelector(BaseModel, is_instance=False)

    value = param.List(default=[], class_=BaseModel)

    def __init__(self, **params):
        super().__init__(**params)
        self._update_value()
        self.param.watch(self._update_value, "value")

    def _update_item(self, event):
        self._updating_item = True
        try:
            self.param.trigger('value')
        finally:
            self._updating_item = False

    def _update_value(self, event: param.Event = None):
        if self._updating_item:
            return

        value = event.new if event else self.value
        self._composite[:] = [f"## {self.name}"]

        if value is not None:
            for i, doc in enumerate(self.value):
                remove_button = Button(name="Delete", button_type="danger")
                remove_button.on_click(self._remove_cb(i))
                editor = PydanticModelEditorCard(
                    value=doc, name=str(i), extra_widgets=[remove_button]
                )
                editor.param.watch(self._update_item, 'value')
                self._composite.append(editor)

        if self.class_ is not None:
            append_button = Button(name="➕")
            append_button.on_click(self._append_cb)
            self._new_editor = PydanticModelEditorCard(
                class_=self.class_, name="➕", extra_widgets=[append_button]
            )
            self._new_editor._composite.collapsed = True
            self._composite.append(self._new_editor)

        self._composite.append(Divider())

    def _append_cb(self, event: param.Event):
        if self._new_editor.value is not None:
            self.value = self.value + [self._new_editor.value]

    def _remove_cb(self, i):
        def cb(event: param.Event):
            if len(self.value) > i:
                new = list(self.value)
                new.pop(i)
                self.value = new
        return cb


@dispatch(precedence=1)
def get_widget(value: BaseModel, field: Any, **kwargs):
    if field is None:
        return PydanticModelEditor(value=value, **kwargs)

    return PydanticModelEditorCard(value=value, class_=field.outer_type_, **kwargs)


@dispatch(precedence=1)
def get_widget(value: List[BaseModel], field: Any, **kwargs):
    if value is None:
        value = []
    return PydanticModelListEditor(value=value, class_=field.type_, **kwargs)
