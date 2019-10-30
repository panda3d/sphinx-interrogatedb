__version__ = '0.1'

from . import documenters


def _config_inited(app, config):
    # Add the search path from config to interrogatedb.
    from panda3d import interrogatedb as idb

    for dir in config.interrogatedb_search_path:
        idb.interrogate_add_search_directory(dir)


def setup(app):
    app.add_autodocumenter(documenters.TypeDocumenter, override=True)
    app.add_autodocumenter(documenters.FunctionDocumenter, override=True)
    app.add_autodocumenter(documenters.ElementDocumenter, override=True)

    app.add_config_value('interrogatedb_search_path', [], 'env')
    app.add_config_value('autodoc_interrogatedb_mangle_type_names', False, 'env')
    app.add_config_value('autodoc_interrogatedb_mangle_function_names', False, 'env')

    app.add_event('interrogatedb-transform-type-name')
    app.add_event('interrogatedb-transform-function-name')

    app.connect('config-inited', _config_inited)
