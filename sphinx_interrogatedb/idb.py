"""Module for efficient lookups in the interrogate database."""

__all__ = []

from panda3d.interrogatedb import *
import keyword


# Copied from interfaceMakerPythonNative.cxx
METHOD_RENAME_DICT = {
    "operator ==": "__eq__",
    "operator !=": "__ne__",
    "operator << ": "__lshift__",
    "operator >>": "__rshift__",
    "operator <": "__lt__",
    "operator >": "__gt__",
    "operator <=": "__le__",
    "operator >=": "__ge__",
    "operator =": "assign",
    "operator ()": "__call__",
    "operator []": "__getitem__",
    "operator ++unary": "increment",
    "operator ++": "increment",
    "operator --unary": "decrement",
    "operator --": "decrement",
    "operator ^": "__xor__",
    "operator %": "__mod__",
    "operator !": "logicalNot",
    "operator ~unary": "__invert__",
    "operator &": "__and__",
    "operator &&": "logicalAnd",
    "operator |": "__or__",
    "operator ||": "logicalOr",
    "operator +": "__add__",
    "operator -": "__sub__",
    "operator -unary": "__neg__",
    "operator *": "__mul__",
    "operator /": "__div__",
    "operator +=": "__iadd__",
    "operator -=": "__isub__",
    "operator *=": "__imul__",
    "operator /=": "__idiv__",
    "operator ,": "concatenate",
    "operator |=": "__ior__",
    "operator &=": "__iand__",
    "operator ^=": "__ixor__",
    "operator ~=": "bitwiseNotEqual",
    "operator ->": "dereference",
    "operator <<=": "__ilshift__",
    "operator >>=": "__irshift__",
    "operator typecast bool": "__nonzero__",
    "__nonzero__": "__nonzero__",
    "__reduce__": "__reduce__",
    "__reduce_persist__": "__reduce_persist__",
    "__copy__": "__copy__",
    "__deepcopy__": "__deepcopy__",
    "print": "Cprint",
    "CInterval.set_t": "_priv__cSetT",
}


def _translate_type_name(name, mangle=False):
    # Equivalent to C++ classNameFromCppName
    class_name = ""
    bad_chars = "!@#$%^&*()<>,.-=+~{}? "
    next_cap = False
    next_uscore = False
    first_char = mangle

    for chr in name:
        if (chr == '_' or chr == ' ') and mangle:
            next_cap = True
        elif chr in bad_chars:
            next_uscore = not mangle
        elif next_cap or first_char:
            class_name += chr.upper()
            next_cap = False
            first_char = False
        elif next_uscore:
            class_name += '_'
            next_uscore = False
            class_name += chr
        else:
            class_name += chr

    return class_name


def _translate_function_name(name, mangle=False):
    # More-or-less esquivalent to C++ methodNameFromCppName
    if name.startswith("__"):
        return name

    if name in METHOD_RENAME_DICT:
        return METHOD_RENAME_DICT[name]

    method_name = ""
    bad_chars = "!@#$%^&*()<>,.-=+~{}? "
    next_cap = False

    for chr in name:
        if (chr == '_' or chr == ' ') and mangle:
            next_cap = True
        elif chr in bad_chars:
            if not mangle:
                method_name += '_'
        elif next_cap:
            method_name += chr.upper()
            next_cap = False
        else:
            method_name += chr

    # Mangle names that happen to be python keywords so they are not anymore
    if keyword.iskeyword(method_name):
        return '_' + method_name
    else:
        return method_name


# These caches map ("modname", name) to a global type and (index, name) to a
# nested type.
_type_cache = {}
_func_cache = {}
_mseq_cache = {}
_elem_cache = {}
_modules = set()

_num_types = 0
_num_funcs = 0


def _store_type(parent, itype):
    """Recurses through the type tree to pick up nested types."""

    name = interrogate_type_name(itype)
    if not name:
        # Ignore anonymous types
        return

    mangled_name1 = _translate_type_name(name, False)
    mangled_name2 = _translate_type_name(name, True)

    _type_cache[(parent, mangled_name1)] = itype
    _type_cache[(parent, mangled_name2)] = itype

    for i in range(interrogate_type_number_of_nested_types(itype)):
        itype2 = interrogate_type_get_nested_type(itype, i)
        _store_type(itype, itype2)


def _refresh_cache():
    """Makes sure that the cache dictionaries are up-to-date."""
    global _num_types, _num_funcs

    num_types = interrogate_number_of_global_types()
    num_funcs = interrogate_number_of_functions()

    if num_types != _num_types:
        for i in range(num_types):
            itype = interrogate_get_global_type(i)
            if interrogate_type_outer_class(itype):
                continue
            modname = interrogate_type_module_name(itype)
            _modules.add(modname)
            _store_type(modname, itype)

        _num_types = num_types

    if num_funcs != _num_funcs:
        for i in range(num_funcs):
            ifunc = interrogate_get_function(i)
            parent = interrogate_function_class(ifunc)
            if not parent:
                parent = interrogate_function_module_name(ifunc)
                _modules.add(parent)

            # Store it by both the original and mangled name.
            name = interrogate_function_name(ifunc)
            mangled_name1 = _translate_function_name(name, False)
            _func_cache[(parent, mangled_name1)] = ifunc
            if not name.startswith('~'):
                mangled_name2 = _translate_function_name(name, True)
                _func_cache[(parent, mangled_name2)] = ifunc

        _num_funcs = num_funcs


def _get_ancestor_types(itype):
    """Returns all derived types of the given type."""

    for i in range(interrogate_type_number_of_derivations(itype)):
        ibase = interrogate_type_get_derivation(itype, i)
        yield ibase
        yield from _get_ancestor_types(ibase)


def lookup_type(module, path):
    _refresh_cache()
    itype = module

    for p in path:
        itype = _type_cache.get((itype, p))
        if not itype:
            return None

    return itype


def lookup_function(module, path):
    if len(path) > 1:
        itype = lookup_type(module, path[:-1])
        if not itype:
            return None

        if path[-1] == '__init__':
            return interrogate_type_get_constructor(itype, 0)
    else:
        itype = module

    _refresh_cache()
    result = _func_cache.get((itype, path[-1]))
    if result:
        return result

    if itype != module:
        # Try looking up in base types.
        for ibase in _get_ancestor_types(itype):
            result = _func_cache.get((ibase, path[-1]))
            if result:
                return result

    return None


def lookup_make_seq(module, path):
    itype = lookup_type(module, path[:-1])
    if not type:
        return None

    name = path[-1]
    key = (itype, name)
    iseq = _mseq_cache.get(key)
    if iseq:
        return iseq

    for i in range(interrogate_type_number_of_make_seqs(itype)):
        iseq = interrogate_type_get_make_seq(itype, i)
        seq_name = interrogate_make_seq_seq_name(iseq)
        if _translate_function_name(seq_name, mangle=True) == name or \
           _translate_function_name(seq_name, mangle=False) == name:
            _mseq_cache[key] = iseq
            return iseq


def lookup_element(module, path):
    itype = lookup_type(module, path[:-1])
    if not type:
        return None

    name = path[-1]
    key = (itype, name)
    ielem = _elem_cache.get(key)
    if ielem:
        return ielem

    for i in range(interrogate_type_number_of_elements(itype)):
        ielem = interrogate_type_get_element(itype, i)
        if interrogate_element_name(ielem) == name:
            _elem_cache[key] = ielem
            return ielem


def has_module(name):
    """Returns True if the given module is known to be produced by
    interrogate.
    """
    _refresh_cache()
    return name in _modules


def get_type_name(itype, *, scoped=False, mangle=False):
    """Returns the type name of a given type, as it should appear to the
    scripting language."""

    name = _translate_type_name(interrogate_type_name(itype), mangle)

    if scoped:
        parent = interrogate_type_outer_class(itype)
        if parent:
            name = get_type_name(parent, scoped=True, mangle=mangle) + '.' + name

    return name


def get_function_name(ifunc, *, scoped=False, mangle=False):
    """Returns the name of a given function, as it should appear in the
    scripting language."""

    name = _translate_function_name(interrogate_function_name(ifunc), mangle)

    if scoped:
        parent = interrogate_function_class(ifunc)
        if parent:
            name = get_type_name(parent, scoped=True, mangle=mangle) + '.' + name

    return name


def get_make_seq_name(iseq, *, mangle=False):
    """Returns the name of a given make-seq, as it should appear in the
    scripting language."""

    name = _translate_function_name(interrogate_make_seq_seq_name(iseq), mangle)
    return name


def get_element_name(ielem):
    """Returns the name of a given element, as it should appear in the
    scripting language."""

    return interrogate_element_name(ielem)
