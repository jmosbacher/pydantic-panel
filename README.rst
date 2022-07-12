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
This is just a small little porject i made for my own use, its limited in scope and probably filled with bugs, USE AT YOUR OWN RISK.
I will continue to add support for more types as I need them but feel free to open issues with requests or better yet PRs with implementations.


* Free software: MIT
* Documentation: https://pydantic-panel.readthedocs.io.


Basic Usage
-----------

If you import `pydantic_panel`, it will register the widget automatically using the `panel.BasePane.applies` interface.
After importing, calling `panel.panel(model)` will return a `panel.CompositeWidget` whos value is the model.
When you change one of the sub-widget values, the new value is validated/coerced using the corresponding pydantic field and if it passes validation/coercion the new value is set on the model itself.
This is a one-way sync, if the model field values are changed via code, it does not sync the widgets.
Nested models and `List[BaseModel]` are supported, `Dict[str,BaseModel]` is trivial to also implement so will probably get around to that soon.


.. code-block:: python
    
    import panel as pn
    import pydantic_panel

    class SomeModel(pydantic.BaseModel):
        name: str
        value: float
    
    w = pn.panel(SomeModel) # all widget values will be None
    w = pn.panel(SomeModel(name='meaning', value=42)) # widget values will be the same as the model instance
    >>> w
        # This will display widgets to edit the model in a notebook

    >>> w.value
        # This will be None if the widgets have not yet been set to values
        # if all the required fields have been set, this will be an instance of SomeModel
        # with the validated attribute values from the widgets



Features
--------

* TODO

Credits
-------

This package was created with Cookiecutter_ and the `briggySmalls/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`briggySmalls/cookiecutter-pypackage`: https://github.com/briggySmalls/cookiecutter-pypackage
