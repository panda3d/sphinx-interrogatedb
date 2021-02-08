__version__ = '1.2.0'
__all__ = []

from . import documenters


def _config_inited(app, config):
    # Add the search path from config to interrogatedb.
    from panda3d import interrogatedb as idb

    for dir in config.interrogatedb_search_path:
        idb.interrogate_add_search_directory(dir)


def setup(app):
    for doc in [documenters.TypeDocumenter,
                documenters.FunctionDocumenter,
                documenters.MakeSeqDocumenter,
                documenters.ElementDocumenter]:
        app.add_autodocumenter(doc, override=True)

    app.add_config_value('interrogatedb_search_path', [], 'env')
    app.add_config_value('autodoc_interrogatedb_mangle_type_names', False, 'env')
    app.add_config_value('autodoc_interrogatedb_mangle_function_names', False, 'env')
    app.add_config_value('autodoc_interrogatedb_type_annotations', True, 'env')
    app.add_config_value('autodoc_interrogatedb_add_rtype', False, 'env')

    app.connect('config-inited', _config_inited)
