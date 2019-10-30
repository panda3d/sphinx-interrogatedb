sphinx-interrogatedb
====================

This is a [Sphinx](https://www.sphinx-doc.org/) extension that provides
autodoc support for modules created by interrogate, by augmenting it with
information provided by interrogate databases (.in files).

Usage
-----

To make use of this extension, the following steps are needed:

1. Install the module using pip.
```
pip install sphinx-interrogatedb
```
2. Enable it in `conf.py`.
```python
extensions = ['sphinx.ext.autodoc', 'sphinx_interrogatedb']
```
3. Configure the search path for interrogatedb files.
```python
interrogate_db_search_path = ['dir/containing/in/files/']
```
4. Just use autodoc, autosummary or [autopackagesummary](https://pypi.org/project/sphinx-autopackagesummary/)
as you would normally, and the .in files will automatically be processed.

Configuration
-------------

The following configuration options are supported:

* `interrogatedb_search_path`: list of folders to search for .in files.
* `autodoc_interrogatedb_mangle_type_names`: if True, converts type names in
  the way that interrogate's python-native back-end does by default.
* `autodoc_interrogatedb_mangle_type_names`: if True, converts type names from
  snake-case to camel-case.  False by default.

Events
------

To customize the names of types or functions, you can hook the
`interrogatedb-transform-type-name` and `interrogatedb-transform-function-name`
events.  They are given the original (un-mangled) type name.  If they return a
string, it is assumed to be the new type name.  If they wish to leave the type
unchanged, they should return None.

For example, if you wanted to show occurrences of a type named `vector_uchar`
as `bytes` instead, your conf.py file could look like this:

```python

def on_transform_type_name(app, type_name):
    if type_name == 'vector_uchar':
        return 'bytes'


def setup(app):
    app.connect('interrogatedb-transform-type-name', on_transform_type_name)
```

License
-------

This extension has been licensed under the terms of the Modified BSD License.
