from sphinx.ext import autodoc
from sphinx.util import logging
from sphinx.locale import _, __
from panda3d.interrogatedb import *
import inspect

from . import mangle

logger = logging.getLogger(__name__)

ITYPE = object()
IFUNC = object()
IELEM = object()


def is_interrogate_module(modname):
    """Returns true if the given module is an interrogate module."""

    for i in range(interrogate_number_of_global_types()):
        itype = interrogate_get_global_type(i)
        if interrogate_type_module_name(itype) == modname:
            return True

    return False


def transformed_type_name(env, itype, scoped=False):
    """Given an interrogate type index, returns the name of the type as it
    should be presented to Python users."""

    while interrogate_type_is_wrapped(itype):
        itype = interrogate_type_wrapped_type(itype)

    if scoped and interrogate_type_is_nested(itype):
        parent = interrogate_type_outer_class(itype)
        return transformed_type_name(env, parent, scoped=True) \
            + '.' \
            + transformed_type_name(env, itype)

    type_name = interrogate_type_name(itype)
    if type_name in ("PyObject", "_object"):
        return "object"
    elif type_name in ("PN_stdfloat", type_name == "double"):
        return "float"

    if interrogate_type_is_atomic(itype):
        token = interrogate_type_atomic_token(itype)
        if token == 7:
            return 'str'
        else:
            return type_name

    new_name = env.app and \
        env.app.emit_firstresult('interrogate-transform-type-name', type_name)
    if new_name is not None:
        return new_name

    if env.app.config.autodoc_interrogatedb_mangle_type_names:
        return mangle.mangle_type_name(type_name)

    return type_name


def transformed_function_name(env, ifunc, scoped=False):
    if scoped:
        parent = interrogate_function_class(ifunc)
        if parent:
            return transformed_type_name(env, parent) + '.' + transformed_function_name(env, ifunc)

    func_name = interrogate_function_name(ifunc)
    new_name = env.app and \
        env.app.emit_firstresult('interrogate-transform-function-name', func_name)
    if new_name is not None:
        return new_name

    if env.app.config.autodoc_interrogatedb_mangle_function_names:
        return mangle.mangle_function_name(func_name)

    return func_name


class TypeDocumenter(autodoc.ClassDocumenter):
    """
    Interrogate type.
    """

    # objtype MUST be 'class' for autosummary to list it.
    objtype = 'class'
    directivetype = 'class'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        if member is ITYPE:
            # Nested type
            return True

        if not isinstance(member, type):
            return False

        if not is_interrogate_module(member.__module__):
            return False

        if isinstance(parent, cls):
            return True
        elif isinstance(parent, autodoc.ModuleDocumenter):
            return member.__module__ == parent.name
        else:
            return False

    def import_object(self):
        """Looks up the object in the interrogate database, storing the type
        index in self.itype.  Returns True if found, False otherwise."""

        scoped_name = '.'.join(self.objpath)

        for i in range(interrogate_number_of_types()):
            itype = interrogate_get_type(i)
            if interrogate_type_module_name(itype) == self.modname and \
               transformed_type_name(self.env, itype, scoped=True) == scoped_name:
                self.itype = itype
                self.doc_as_attr = False
                return True

        logger.warning("failed to find '%s' in interrogate database for module '%s'" % (scoped_name, self.modname), type='autodoc')
        return False

    def get_real_modname(self):
        return interrogate_type_module_name(self.itype)

    def check_module(self):
        #if self.options.imported_members:
        #    return True
        assert False

        modname = interrogate_type_module_name(self.itype)
        return modname == self.modname

    def format_args(self, **kwargs):
        # We don't bother putting constructor args in the class signature;
        # there may be multiple overloads, and they are better documented
        # as part of the __init__ signature.
        return None

    def add_directive_header(self, sig):
        sourcename = self.get_sourcename()

        # Sphinx doesn't have Python enums, we'll just cheat and map it to a
        # C++ enum instead.
        if interrogate_type_is_enum(self.itype):
            self.add_line('.. cpp:enum:: ' + self.objpath[-1], sourcename)
            if self.options.noindex:
                self.add_line('   :noindex:', sourcename)
        else:
            super().add_directive_header(sig)

        if self.options.show_inheritance:
            self.add_line('', sourcename)

            nderivs = interrogate_type_number_of_derivations(self.itype)
            if nderivs > 0:
                bases = [
                    ':class:`%s`' % transformed_type_name(
                        self.env,
                        interrogate_type_get_derivation(self.itype, i)
                    ) for i in range(nderivs)
                ]
                self.add_line('   ' + _('Bases: %s') % ', '.join(bases),
                              sourcename)

    def get_doc(self):
        return [interrogate_type_comment(self.itype).splitlines() + ['']]

    def add_content(self, more_content, no_docstring=False):
        super().add_content(more_content, no_docstring)

        sourcename = self.get_sourcename()

        if interrogate_type_is_enum(self.itype):
            for i in range(interrogate_type_number_of_enum_values(self.itype)):
                name = interrogate_type_enum_value_name(self.itype, i)
                value = interrogate_type_enum_value(self.itype, i)
                comment = interrogate_type_enum_value_comment(self.itype, i)

                #FIXME: let's do these as proper members, actually.
                # Then comments can also be handled as normal.
                self.add_line('.. cpp:enumerator:: {0} = {1}'.format(name, value), sourcename)
                self.add_line('', sourcename)
                self.add_line('   ' + comment.replace('// ', ' ').strip(), sourcename)
                self.add_line('', sourcename)

    def get_object_members(self, want_all):
        ret = []

        for i in range(interrogate_type_number_of_constructors(self.itype)):
            ifunc = interrogate_type_get_constructor(self.itype, i)
            ret.append(('__init__', IFUNC))

        for i in range(interrogate_type_number_of_methods(self.itype)):
            ifunc = interrogate_type_get_method(self.itype, i)
            ret.append((transformed_function_name(self.env, ifunc), IFUNC))

        for i in range(interrogate_type_number_of_make_seqs(self.itype)):
            iseq = interrogate_type_get_make_seq(self.itype, i)
            ret.append((interrogate_make_seq_seq_name(iseq), IFUNC))

        for i in range(interrogate_type_number_of_elements(self.itype)):
            ielem = interrogate_type_get_element(self.itype, i)
            ret.append((interrogate_element_name(ielem), IELEM))

        for i in range(interrogate_type_number_of_nested_types(self.itype)):
            itype2 = interrogate_type_get_nested_type(self.itype, i)
            ret.append((transformed_type_name(self.env, itype2), ITYPE))

        return False, ret


class FunctionDocumenter(autodoc.ModuleLevelDocumenter):
    """
    Interrogate function.
    """

    objtype = 'function'
    directivetype = 'method'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return member is IFUNC

    def import_object(self):
        """Looks up the object in the interrogate database, storing the type
        index in self.ifunc.  Returns True if found, False otherwise."""

        module_name = self.modname
        if self.objpath[-1] == '__init__':
            scoped_name = '.'.join(self.objpath[:-1] + [self.objpath[-2]])
        else:
            scoped_name = '.'.join(self.objpath)

        for i in range(interrogate_number_of_functions()):
            ifunc = interrogate_get_function(i)
            if interrogate_function_module_name(ifunc) == module_name and \
               transformed_function_name(self.env, ifunc, scoped=True) == scoped_name:
                self.ifunc = ifunc
                return True

        logger.warning("failed to find '%s' in interrogate database for module '%s'" % (scoped_name, module_name), type='autodoc')
        return False

    def get_real_modname(self):
        return interrogate_function_module_name(self.ifunc)

    def check_module(self):
        modname = interrogate_function_module_name(self.ifunc)
        return modname == self.modname

    def format_args(self, iwrap, **kwargs):
        sig = "("
        for i in range(interrogate_wrapper_number_of_parameters(iwrap)):
            if not interrogate_wrapper_parameter_is_this(iwrap, i):
                if sig != "(":
                    sig += ", "
                sig += interrogate_wrapper_parameter_name(iwrap, i)
                sig += " : "
                sig += transformed_type_name(self.env, interrogate_wrapper_parameter_type(iwrap, i))
        sig += ")"

        if self.objpath[-1] != '__init__' and interrogate_wrapper_has_return_value(iwrap):
            sig += " -> " + transformed_type_name(self.env, interrogate_wrapper_return_type(iwrap))
        else:
            sig += " -> None"

        return sig

    def add_directive_header(self, sig):
        super().add_directive_header(sig)

        sourcename = self.get_sourcename()

        # If one overload is a staticmethod, all of them are.
        if self.objpath[-1] == '__init__':
            is_static = False
        else:
            is_static = True
            for i in range(interrogate_function_number_of_python_wrappers(self.ifunc)):
                iwrap = interrogate_function_python_wrapper(self.ifunc, i)

                if interrogate_wrapper_number_of_parameters(iwrap) > 0 and \
                   interrogate_wrapper_parameter_is_this(iwrap, 0):
                    is_static = False

        if is_static:
            self.add_line('   :staticmethod:', sourcename)

    def get_doc(self):
        return [interrogate_function_comment(self.ifunc).splitlines() + ['']]

    def generate(self, more_content=None, real_modname=None,
                 check_module=False, all_members=False):
        if not self.parse_name():
            # need a module to import
            logger.warning(
                __('don\'t know which module to import for autodocumenting '
                   '%r (try placing a "module" or "currentmodule" directive '
                   'in the document, or giving an explicit module name)') %
                self.name, type='autodoc')
            return

        # Grab the stuff from the interrogate database
        if not self.import_object():
            return

        # check __module__ of object (for members not given explicitly)
        if check_module:
            if not self.check_module():
                return

        sourcename = self.get_sourcename()

        # Output each overload separately.
        for i in range(interrogate_function_number_of_python_wrappers(self.ifunc)):
            iwrap = interrogate_function_python_wrapper(self.ifunc, i)
            sig = self.format_signature(iwrap=iwrap)

            # make sure that the result starts with an empty line.  This is
            # necessary for some situations where another directive preprocesses
            # reST and no starting newline is present
            self.add_line('', sourcename)

            # generate the directive header and options, if applicable
            self.add_directive_header(sig)
            self.add_line('', sourcename)

            # e.g. the module directive doesn't have content
            self.indent += self.content_indent

            docstrings = []
            if interrogate_wrapper_has_comment(iwrap):
                docstrings.append(interrogate_wrapper_comment(iwrap).splitlines())
            if not docstrings:
                # append at least a dummy docstring, so that the event
                # autodoc-process-docstring is fired and can add some
                # content if desired
                docstrings.append([])
            for i, line in enumerate(self.process_doc(docstrings)):
                self.add_line(line, sourcename, i)

            self.indent = self.indent[:-len(self.content_indent)]


class ElementDocumenter(autodoc.ClassLevelDocumenter):
    """
    Interrogate element.
    """

    objtype = 'attribute'
    directivetype = 'attribute'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return member is IELEM

    def import_object(self):
        """Looks up the object in the interrogate database, storing the type
        index in self.ifunc.  Returns True if found, False otherwise."""

        #TODO: this way of getting scoped name does not take type name
        # transformation into account.
        module_name = self.modname
        type_name = '::'.join(self.objpath[:-1])
        elem_name = self.objpath[-1]

        # Find the type first.
        itype = interrogate_get_type_by_scoped_name(type_name)
        if not itype or interrogate_type_module_name(itype) != module_name:
            logger.warning("failed to find '%s' in interrogate database for module '%s'" % (type_name, module_name), type='autodoc')
            return False

        # Find the element under this type.
        for i in range(interrogate_type_number_of_elements(itype)):
            ielem = interrogate_type_get_element(itype, i)
            if interrogate_element_name(ielem) == elem_name:
                self.itype = itype
                self.ielem = ielem
                return True

        return False

    def get_real_modname(self):
        return interrogate_type_module_name(self.itype)

    def check_module(self):
        modname = interrogate_type_module_name(self.itype)
        return modname == self.modname

    def get_doc(self):
        docstrings = []

        if interrogate_element_has_comment(self.ielem):
            elem_doc = interrogate_element_comment(self.ielem)
            docstrings.append(elem_doc.splitlines())

        if interrogate_element_has_getter(self.ielem):
            getter = interrogate_element_getter(self.ielem)
            getter_doc = interrogate_function_comment(getter)
            docstrings.append(getter_doc.splitlines())

            if interrogate_element_has_setter(self.ielem):
                setter = interrogate_element_setter(self.ielem)
                setter_doc = interrogate_function_comment(setter)
                if setter_doc and setter_doc != getter_doc:
                    docstrings.append(setter_doc.splitlines())

        return docstrings
