==============
pydantic-panel
==============


.. image:: https://img.shields.io/pypi/v/pydantic_panel.svg
        :target: https://pypi.python.org/pypi/pydantic_panel

.. image:: https://img.shields.io/travis/jmosbacher/pydantic_panel.svg
        :target: https://travis-ci.com/jmosbacher/pydantic_panel

.. image:: https://readthedocs.org/projects/pydantic-panel/badge/?version=latest
        :target: https://pydantic-panel.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Edit pydantic models with panel.

This is just a small little project i made mostly for my own use and decided to share.
Its limited in scope and probably still has bugs, USE AT YOUR OWN RISK.

I will continue to add support for more types as I need them but feel free to 
open issues with feature requests or better yet PRs with implementations.


* Free software: MIT
* Documentation: https://pydantic-panel.readthedocs.io.

Getting Started
---------------

Step 1 - Install 

.. code-block::

    pip install pydantic-panel


Step 2 - Import pydantic_panel and add your models to layouts!

.. code-block:: python
    
    import pydantic
    import panel as pn
    import pydantic_panel

    class SomeModel(pydantic.BaseModel):
        name: str
        value: float

    widget = pn.panel(SomeModel)

    layout = pn.Column(widget, widget.json)
    layout.servable()


Now edit 

Basic Usage
-----------

If you import `pydantic_panel`, it will register the widget automatically using the `panel.BasePane.applies` interface.
After importing, calling `panel.panel(model)` will return a `panel.CompositeWidget` whos value is the model.
When you change one of the sub-widget values, the new value is validated/coerced using the corresponding pydantic
field and if it passes validation/coercion the new value is set on the model itself.
By default this is a one-way sync, if the model field values are changed via code, it does not sync the widgets.
If you want biderectional sync, you can pass `bidirectional = True` to the widget constructor, this will patch the model 
to sync changes to the widgets but this may break without warning if pydantic change the internals of 
their `__setattr__` method.


.. code-block:: python

    import panel as pn
    import pydantic_panel

    class SomeModel(pydantic.BaseModel):
        name: str
        value: float

    # when passing a model class, 
    # all widget values will be None including the composite widget value
    w = pn.panel(SomeModel)
    
    # if you pass a model instance 
    # widget values will be the same as the model instance
    inst = SomeModel(name='meaning', value=42)
    w = pn.panel(inst)

    # This will display widgets to e.g. edit the model in a notebook
    w

    # This will return True
    inst is w.value

    # This will be None if the widgets have not yet been set to values
    # if all the required fields have been set, this will be an instance of SomeModel
    # with the validated attribute values from the widgets
    w.value


The `pn.panel` method will return a widget which can be used as part of a larger application or as just 
a user friendly way to edit your model data in the notebook.

Customizing widgets
-------------------

You can add or change the widgets used for a given type by hooking into the dispatch
mechanism (we use plum-dispatch). This can be used to override the widget used for a supported
type or to add supprt for a new type.


.. code-block:: python

    from pydantic_panel import get_widget
    from pydantic import FieldInfo

    # precedence = 1 will ensure this function will be called
    # instead of the default which has precedence = 0
    @get_widget.dispatch(precedence=1)
    def get_widget(value: MY_TYPE, field: FieldInfo, **kwargs):
        # extract relavent info from the pydantic field info here.

        # return your favorite widget
        return MY_FAVORITE_WIDGET(value=value, **kwargs)


Supporting non-serializable types
---------------------------------

Panel encodes the data sent to the widget using json serialization. 
If your type is not json serializable, you can have pydantic-panel convert
the data to a json-serializable object before its passed to the widget. To add
this conversion, register a conversion function using the `json_serializable.dispatch`
decorator

.. code-block:: python

    from pydantic_panel import json_serializable

    # precedence = 1 will ensure this function will be called
    # instead of the default which has precedence = 0
    @json_serializable.dispatch(precedence=1)
    def json_serializable(value: TYPE):
        # convert to a serializable object
        value = some_function(value)
        return value


Supported types
---------------

* int
* float
* str
* list
* tuple
* dict
* datetime.datetime
* BaseModel
* List[BaseModel]
* pandas.Interval
* numpy.ndarray

FAQ
---

Q: Why did you decide to use CompositWidget instead of Pane like Param uses?

A: Nested models. This is a recursive problem, so I was looking for a recursive solution. By using a Widget to
display models, all fields are treated equally. A field of type BaseModel is edited with a widget that has a `.value` 
attribute just like any other field and therefore requires no special treatment. When the parent collects the values of its children 
it just reads the `widget.value` attribute and does not need to check whether the value is nested or not. At every level 
of the recursion the widget only has to care about the fields on its model class and watch only the `.value` attribute of
its children widgets for changes.


Features
--------

* TODO

Credits
-------

This package was created with Cookiecutter_ and the `briggySmalls/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`briggySmalls/cookiecutter-pypackage`: https://github.com/briggySmalls/cookiecutter-pypackage
