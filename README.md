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
interrogatedb_search_path = ['dir/containing/in/files/']
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
* `autodoc_interrogatedb_type_annotations`: if True, shows argument and return
  types in function signatures using type hint syntax.  True by default.
* `autodoc_interrogatedb_add_rtype`: if True, adds an `:rtype:` directive to
  the bodies of docstrings with the return type.  True by default.

License
-------

This extension has been licensed under the terms of the Modified BSD License.
