__all__ = [
    "TypeDocumenter", "FunctionDocumenter", "MakeSeqDocumenter",
    "ElementDocumenter",
]

from sphinx.ext import autodoc
from sphinx.util import logging
from sphinx.locale import _, __
from docutils.parsers.rst import directives
from panda3d.interrogatedb import *
import types
import builtins

from . import idb

logger = logging.getLogger(__name__)

# These constants are used by get_object_members to flag members of interrogate
# types that should be handled by the respective documenters in this module.
ITYPE = object()
IFUNC = object()
IELEM = object()
IMSEQ = object()


class TypeDocumenter(autodoc.ClassDocumenter):
    """
    Interrogate type.
    """

    # We override the built-in handler for "class", and dispatch down to the
    # base class for types outside of interrogate modules.
    objtype = 'class'
    directivetype = 'class'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        if member is ITYPE:
            # Nested type
            return True

        return super().can_document_member(member, membername, isattr, parent)

    def import_object(self):
        """Looks up the object in the interrogate database, storing the type
        index in self.itype.  Returns True if found, False otherwise."""

        if not idb.has_module(self.modname):
            # Not an interrogate type; the base class should handle this one.
            self.__class__ = autodoc.ClassDocumenter
            return autodoc.ClassDocumenter.import_object(self)

        itype = idb.lookup_type(self.modname, self.objpath)
        if not itype:
            logger.warning("failed to find type '%s' in interrogate database" % (self.fullname), type='autodoc')
            return False

        # Unwrap typedef.
        #while interrogate_type_is_typedef(itype):
        #    itype = interrogate_type_wrapped_type(itype)

        self.itype = itype

        # Document as an attribute if this is just an alias to the "real" name.
        #real_name = idb.get_type_name(itype, mangle=self.env.config.autodoc_interrogatedb_mangle_type_names)
        #self.doc_as_attr = (real_name != self.objpath[-1])
        self.doc_as_attr = False
        return True

    def get_real_modname(self):
        return interrogate_type_module_name(self.itype)

    def check_module(self):
        return self.get_real_modname() == self.modname

    def format_args(self, **kwargs):
        # We don't bother putting constructor args in the class signature;
        # there may be multiple overloads, and they are better documented
        # as part of the __init__ signature.
        return None

    def add_directive_header(self, sig):
        sourcename = self.get_sourcename()

        domain = getattr(self, 'domain', 'py')

        # Sphinx doesn't have Python enums, we'll just cheat and map it to a
        # C++ enum instead.
        if interrogate_type_is_enum(self.itype):
            self.add_line('.. cpp:enum:: ' + self.objpath[-1], sourcename)
            if self.options.noindex:
                self.add_line('   :noindex:', sourcename)

        elif domain == 'cpp' and interrogate_type_is_typedef(self.itype):
            wrapped_itype = interrogate_type_wrapped_type(self.itype)
            self.add_line('.. cpp:type:: {0} {1}'.format(interrogate_type_scoped_name(wrapped_itype), interrogate_type_scoped_name(self.itype)), sourcename)
            if self.options.noindex:
                self.add_line('   :noindex:', sourcename)

        elif domain == 'cpp' and interrogate_type_is_struct(self.itype):
            self.add_line('.. cpp:struct:: ' + interrogate_type_name(self.itype), sourcename)
            if self.options.noindex:
                self.add_line('   :noindex:', sourcename)

        elif domain == 'cpp' and interrogate_type_is_class(self.itype):
            self.add_line('.. cpp:class:: ' + interrogate_type_name(self.itype), sourcename)
            if self.options.noindex:
                self.add_line('   :noindex:', sourcename)

        else:
            super().add_directive_header(sig)

        if not self.doc_as_attr and self.options.show_inheritance and not interrogate_type_is_typedef(self.itype):
            self.add_line('', sourcename)

            nderivs = interrogate_type_number_of_derivations(self.itype)
            if nderivs > 0:
                if domain == 'cpp':
                    bases = [
                        ':{}:class:`{}`'.format(domain,
                            interrogate_type_name(interrogate_type_get_derivation(self.itype, i)).replace('<', '\\<')
                        ) for i in range(nderivs)
                    ]
                else:
                    bases = [
                        ':{}:class:`{}`'.format(domain, idb.get_type_name(
                            interrogate_type_get_derivation(self.itype, i),
                            scoped=True,
                            mangle=self.env.config.autodoc_interrogatedb_mangle_type_names,
                        )) for i in range(nderivs)
                    ]
                self.add_line('   ' + _('Bases: %s') % ', '.join(bases),
                              sourcename)

    def get_doc(self):
        return [interrogate_type_comment(self.itype).splitlines() + ['']]

    def add_content(self, more_content, no_docstring=False):
        sourcename = self.get_sourcename()

        domain = getattr(self, 'domain', 'py')

        if interrogate_type_is_typedef(self.itype):
            # Document as alias.
            wrapped_itype = interrogate_type_wrapped_type(self.itype)
            if domain == 'cpp':
                type_name = interrogate_type_name(wrapped_itype)
                type_name = type_name.replace('<', '\\<')

                if interrogate_type_is_typedef(wrapped_itype):
                    typ = 'type'
                elif interrogate_type_is_enum(wrapped_itype):
                    typ = 'enum'
                elif interrogate_type_is_struct(wrapped_itype):
                    typ = 'struct'
                elif interrogate_type_is_class(wrapped_itype):
                    typ = 'class'
                elif interrogate_type_is_union(wrapped_itype):
                    typ = 'union'
                else:
                    return
            else:
                type_name = idb.get_type_name(wrapped_itype, mangle=self.env.config.autodoc_interrogatedb_mangle_type_names)
                typ = 'class'

            self.add_line('alias of :{}:{}:`{}`'.format(domain, typ, type_name), sourcename)
            return

        super().add_content(more_content, no_docstring)

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

    def filter_members(self, members, want_all):
        return [(a, b, False) for a, b in members]

    def get_object_members(self, want_all):
        ret = []

        domain = getattr(self, 'domain', 'py')

        if interrogate_type_number_of_constructors(self.itype) > 0:
            ret.append(('__init__', IFUNC))

        mangle_types = domain != 'cpp' and self.env.config.autodoc_interrogatedb_mangle_type_names
        mangle_funcs = domain != 'cpp' and self.env.config.autodoc_interrogatedb_mangle_function_names

        for i in range(interrogate_type_number_of_methods(self.itype)):
            ifunc = interrogate_type_get_method(self.itype, i)
            ret.append((idb.get_function_name(ifunc, mangle=mangle_funcs), IFUNC))

        if domain == 'py':
            for i in range(interrogate_type_number_of_make_seqs(self.itype)):
                iseq = interrogate_type_get_make_seq(self.itype, i)
                ret.append((idb.get_make_seq_name(iseq, mangle=mangle_funcs), IMSEQ))

            for i in range(interrogate_type_number_of_elements(self.itype)):
                ielem = interrogate_type_get_element(self.itype, i)
                ret.append((idb.get_element_name(ielem), IELEM))

        for i in range(interrogate_type_number_of_nested_types(self.itype)):
            itype2 = interrogate_type_get_nested_type(self.itype, i)
            if not interrogate_type_name(itype2):
                #FIXME: pull constants from anonymous enums
                continue
            ret.append((idb.get_type_name(itype2, mangle=mangle_types), ITYPE))

        return False, ret

    def generate(self, *args, **kwargs):
        if not hasattr(self, 'domain'):
            domain = self.env.temp_data.get('default_domain')
            if domain:
                self.domain = domain.name

        if not self.parse_name():
            # need a module to import
            logger.warning(
                __('don\'t know which module to import for autodocumenting '
                   '%r (try placing a "module" or "currentmodule" directive '
                   'in the document, or giving an explicit module name)') %
                self.name, type='autodoc')
            return

        # now, import the module and get object to document
        if not self.import_object():
            return

        if not hasattr(self, 'itype'):
            return autodoc.ClassDocumenter.generate(self, *args, **kwargs)

        real_name = idb.get_type_name(self.itype, mangle=False)
        if self.objpath[-1] != real_name:
            # This is an alias, which isn't available in C++, so we have to
            # just redirect to the right page or something.
            sourcename = self.get_sourcename()
            self.add_line('', sourcename)

            domain = getattr(self, 'domain', 'py')
            if domain == 'cpp':
                cpp_name = interrogate_type_name(self.itype)

                if interrogate_type_is_typedef(self.itype):
                    typ = 'type'
                elif interrogate_type_is_enum(self.itype):
                    typ = 'enum'
                elif interrogate_type_is_struct(self.itype):
                    typ = 'struct'
                elif interrogate_type_is_class(self.itype):
                    typ = 'class'
                elif interrogate_type_is_union(self.itype):
                    typ = 'union'
                else:
                    return

                self.add_line('See :cpp:{}:`{}`'.format(typ, cpp_name.replace('<', '\\<')), sourcename)
            else:
                self.add_line('.. class:: ' + self.objpath[-1], sourcename)
                self.add_line('', sourcename)
                self.indent += self.content_indent
                if interrogate_type_is_enum(self.itype):
                    self.add_line('alias of :cpp:enum:`{}`'.format(real_name), sourcename)
                else:
                    self.add_line('alias of :{}:class:`{}`'.format(domain, real_name), sourcename)
                self.indent = self.indent[:-len(self.content_indent)]

            self.add_line('', sourcename)
            return

        super().generate(*args, **kwargs)


class FunctionDocumenter(autodoc.FunctionDocumenter):
    """
    Interrogate function.
    """

    objtype = 'function'
    directivetype = 'function'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        if member is IFUNC:
            # Method.
            return True

        return super().can_document_member(member, membername, isattr, parent)

    def import_object(self):
        """Looks up the function in the interrogate database, storing the
        function index in self.ifunc.  Returns True if found, False otherwise.
        """

        ifunc = idb.lookup_function(self.modname, self.objpath)
        if not ifunc:
            logger.warning("failed to find function '%s' in interrogate database" % (self.fullname), type='autodoc')
            return False

        self.ifunc = ifunc
        if len(self.objpath) > 0:
            self.objtype = 'method'
            self.directivetype = 'method'
        return True

    def get_real_modname(self):
        return interrogate_function_module_name(self.ifunc)

    def check_module(self):
        return self.get_real_modname() == self.modname

    def format_args(self, iwrap, **kwargs):
        # NB. If you get this error:
        # format_args() missing 1 required positional argument: 'iwrap'
        # ...then the problem is that this function raised a TypeError, which
        # Sphinx takes to mean that it should call this again without any
        # arguments passed in.

        show_types = self.env.config.autodoc_interrogatedb_type_annotations

        sig = "("
        for i in range(interrogate_wrapper_number_of_parameters(iwrap)):
            if not interrogate_wrapper_parameter_is_this(iwrap, i):
                if sig != "(":
                    sig += ", "
                sig += interrogate_wrapper_parameter_name(iwrap, i)
                if show_types:
                    sig += ": "
                    sig += self._format_arg_type(interrogate_wrapper_parameter_type(iwrap, i))
        sig += ")"

        if show_types and self.objpath[-1] != '__init__':
            if interrogate_wrapper_has_return_value(iwrap):
                sig += " -> " + self._format_arg_type(interrogate_wrapper_return_type(iwrap))
            else:
                sig += " -> None"

        return sig

    def _format_arg_type(self, itype):
        domain = getattr(self, 'domain', 'py')
        if domain == 'cpp':
            return interrogate_type_scoped_name(itype)

        # Unwrap the type.
        while interrogate_type_is_wrapped(itype):
            itype = interrogate_type_wrapped_type(itype)

        orig_name = interrogate_type_name(itype)
        if orig_name in ("PyObject", "_object"):
            return "object"
        elif orig_name in ("PN_stdfloat", "double"):
            return "float"
        elif orig_name == "vector_uchar":
            return "bytes"

        unwrapped_itype = itype
        while interrogate_type_is_typedef(unwrapped_itype):
            unwrapped_itype = interrogate_type_wrapped_type(unwrapped_itype)

        if interrogate_type_is_atomic(unwrapped_itype):
            token = interrogate_type_atomic_token(unwrapped_itype)
            if token == 1:
                return 'int'
            elif token == 2 or token == 3:
                return 'float'
            elif token == 4:
                return 'bool'
            elif token == 7:
                return 'str'
            elif token == 8:
                return 'int'

        type_name = idb.get_type_name(
            itype,
            mangle=self.env.config.autodoc_interrogatedb_mangle_type_names)

        if domain == 'py':
            if interrogate_function_module_name(self.ifunc) != interrogate_type_module_name(itype):
                return interrogate_type_module_name(itype) + '.' + type_name

        return type_name

    def add_directive_header(self, sig):
        super().add_directive_header(sig)

        sourcename = self.get_sourcename()

        # If one overload is a staticmethod, all of them are.
        if len(self.objpath) <= 1 or self.objpath[-1] == '__init__':
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

        if not idb.has_module(self.modname):
            # Not an interrogate module.  Pass on to parent.
            self.__class__ = autodoc.FunctionDocumenter
            return autodoc.FunctionDocumenter.generate(
                self, more_content, real_modname, check_module, all_members)

        if self.objpath[-1] == 'Dtool_BorrowThisReference':
            # Ignore this.
            return

        # Grab the stuff from the interrogate database
        if not self.import_object():
            return

        # check __module__ of object (for members not given explicitly)
        if check_module:
            if not self.check_module():
                return

        domain = getattr(self, 'domain', None)
        if not domain:
            domain = self.env.temp_data.get('default_domain')
            domain = domain.name if domain else 'py'

        # Do not show this if this is a mere alias.
        if domain == 'cpp':
            real_name = interrogate_function_name(self.ifunc)
            if real_name.startswith('__') and real_name.endswith('__'):
                # This is meant for Python.
                return
        else:
            real_name = idb.get_function_name(self.ifunc, mangle=self.env.config.autodoc_interrogatedb_mangle_function_names)

        if self.objpath[-1] != '__init__' and self.objpath[-1] != real_name:
            return

        sourcename = self.get_sourcename()

        if domain == 'cpp':
            # List the C++ methods instead.
            sigs = interrogate_function_prototype(self.ifunc).strip()
            if not sigs:
                return

            itype = interrogate_function_class(self.ifunc)
            if itype:
                prefix = interrogate_type_scoped_name(itype) + '::'
                prefix = prefix.replace('< std::', '< ')
            else:
                prefix = ''

            for sig in sigs.splitlines():
                if not sig:
                    continue

                if prefix:
                    # Hack to get rid of extra scoping.
                    if sig.startswith(prefix):
                        sig = sig[len(prefix):]

                    sig = sig.replace(' ' + prefix, ' ')
                    sig = sig.replace('&' + prefix, ' &')
                    sig = sig.replace('*' + prefix, ' *')
                    sig = sig.replace(' ::' + prefix, ' ')
                    sig = sig.replace('&::' + prefix, ' &')
                    sig = sig.replace('*::' + prefix, ' *')

                # The inline keyword isn't really interesting to report.
                if sig.startswith("inline "):
                    sig = sig[7:]
                elif sig.startswith("static inline "):
                    sig = sig[14:]

                sig = sig.rstrip(';')
                self.add_line('', sourcename)
                self.add_line('.. cpp:function:: {}'.format(sig), sourcename)

            self.add_line('', sourcename)

            self.indent += self.content_indent

            docstrings = []
            if interrogate_function_has_comment(self.ifunc):
                comment = interrogate_function_comment(self.ifunc) + '\n\n'
                # If it repeats itself, get the first repetition only.
                comment = comment[:(comment + comment).find(comment, 1, -1)]
                docstrings.append(comment.strip().splitlines())
            if not docstrings:
                # append at least a dummy docstring, so that the event
                # autodoc-process-docstring is fired and can add some
                # content if desired
                docstrings.append([])
            for i, line in enumerate(self.process_doc(docstrings)):
                self.add_line(line, sourcename, i)

            self.indent = self.indent[:-len(self.content_indent)]
            return

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

            # Only the first one should be indexed, fixes a warning
            if i > 0:
                self.add_line('   :noindex:', sourcename)

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

            # Should we add an :rtype: ?
            if self.env.config.autodoc_interrogatedb_add_rtype and \
               self.objpath[-1] != '__init__' and \
               interrogate_wrapper_has_return_value(iwrap):
                itype = interrogate_wrapper_return_type(iwrap)
                if itype:
                    type_name = self._format_arg_type(itype)
                    if type_name not in dir(builtins):
                        self.add_line('', sourcename)
                        self.add_line(":rtype: " + type_name, sourcename)
                        self.add_line('', sourcename)

            self.indent = self.indent[:-len(self.content_indent)]


class MakeSeqDocumenter(autodoc.ClassLevelDocumenter):
    """
    Interrogate sequence generator method.
    """

    objtype = 'imakeseq'
    directivetype = 'method'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return member is IMSEQ

    def import_object(self):
        """Looks up the make-seq in the interrogate database, storing the
        make-seq index in self.iseq.  Returns True if found, False otherwise.
        """

        iseq = idb.lookup_make_seq(self.modname, self.objpath)
        if not iseq:
            logger.warning("failed to find make-seq '%s' in interrogate database" % (self.fullname), type='autodoc')
            return False

        self.iseq = iseq
        return True

    def format_args(self, **kwargs):
        if self.env.config.autodoc_interrogatedb_type_annotations:
            return "() -> list"
        else:
            return "()"

    def get_doc(self):
        return [interrogate_make_seq_comment(self.iseq).splitlines() + ['']]


class ElementDocumenter(autodoc.ClassLevelDocumenter):
    """
    Interrogate element.
    """

    objtype = 'ielement'
    directivetype = 'method'

    # Rank this higher than the built-in documenters.
    priority = 20

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return member is IELEM

    def import_object(self):
        """Looks up the object in the interrogate database, storing the element
        index in self.ielem.  Returns True if found, False otherwise."""

        ielem = idb.lookup_element(self.modname, self.objpath)
        if not ielem:
            logger.warning("failed to find element '%s' in interrogate database" % (self.fullname), type='autodoc')
            return False

        self.ielem = ielem
        return True

    def add_directive_header(self, sig):
        super().add_directive_header(sig)

        sourcename = self.get_sourcename()
        self.add_line('   :property:', sourcename)

    def format_args(self):
        if not self.env.config.autodoc_interrogatedb_type_annotations:
            return ""

        itype = interrogate_element_type(self.ielem)
        if itype:
            type_name = self._format_type(itype)
            if type_name:
                if interrogate_element_is_sequence(self.ielem):
                    return "() -> Sequence[{0}]".format(type_name)
                else:
                    return "() -> " + type_name

    def _format_type(self, itype):
        domain = getattr(self, 'domain', 'py')
        if domain == 'cpp':
            return interrogate_type_scoped_name(itype)

        # Unwrap the type.
        while interrogate_type_is_wrapped(itype):
            itype = interrogate_type_wrapped_type(itype)

        orig_name = interrogate_type_name(itype)
        if orig_name in ("PyObject", "_object"):
            return
        elif orig_name in ("PN_stdfloat", "double"):
            return "float"
        elif orig_name == "vector_uchar":
            return "bytes"

        unwrapped_itype = itype
        while interrogate_type_is_typedef(unwrapped_itype):
            unwrapped_itype = interrogate_type_wrapped_type(unwrapped_itype)

        if interrogate_type_is_atomic(unwrapped_itype):
            token = interrogate_type_atomic_token(unwrapped_itype)
            if token == 1:
                return 'int'
            elif token == 2 or token == 3:
                return 'float'
            elif token == 4:
                return 'bool'
            elif token == 7:
                return 'str'
            elif token == 8:
                return 'int'

        return idb.get_type_name(
            itype,
            mangle=self.env.config.autodoc_interrogatedb_mangle_type_names)

    def get_doc(self):
        docstrings = []

        if interrogate_element_has_comment(self.ielem):
            elem_doc = interrogate_element_comment(self.ielem)
            docstrings.append(elem_doc.splitlines())

        return docstrings

    def add_content(self, more_content=[], no_docstring=False):
        super().add_content(more_content, no_docstring)

        sourcename = self.get_sourcename()

        # Add the docstrings of the getter and the setter.
        if interrogate_element_has_getter(self.ielem):
            getter = interrogate_element_getter(self.ielem)
            getter_doc = interrogate_function_comment(getter)
        else:
            getter_doc = ""

        if interrogate_element_has_setter(self.ielem):
            setter = interrogate_element_setter(self.ielem)
            setter_doc = interrogate_function_comment(setter)
        else:
            setter_doc = ""

        if getter_doc or setter_doc:
            self.add_line('', sourcename)

        if getter_doc and setter_doc and getter_doc != setter_doc:
            # In many methods, the only difference between the getter/setter doc
            # is the first word.  If that is so, we can combine the two.
            getter_words = getter_doc.strip().split(' ')
            setter_words = setter_doc.strip().split(' ')
            combined_words = []
            num_different_words = 0
            if len(getter_words) == len(setter_words):
                for getter_word, setter_word in zip(getter_words, setter_words):
                    if getter_word == setter_word:
                        combined_words.append(getter_word)
                    elif not getter_word or not setter_word:
                        word = getter_word or setter_word
                        combined_words.append('(' + word + ')')
                        num_different_words += 1
                    else:
                        combined_words.append(getter_word + '/' + setter_word)
                        num_different_words += 1
            else:
                num_different_words = len(combined_words)

            # Do this only if at most a third of the words have a slash.
            if combined_words and (num_different_words * 3) / len(combined_words) <= 1:
                doc = ' '.join(combined_words)
                docstrings = [doc.splitlines()]
                for line in self.process_doc(docstrings):
                    self.add_line(line, sourcename)
            else:
                # Show both getter and setter docs.
                self.add_line("Getter", sourcename)
                docstrings = [getter_doc.splitlines()]
                for line in self.process_doc(docstrings):
                    self.add_line('   ' + line, sourcename)

                self.add_line("Setter", sourcename)
                docstrings = [setter_doc.splitlines()]
                for line in self.process_doc(docstrings):
                    self.add_line('   ' + line, sourcename)

        elif getter_doc or setter_doc:
            # If we have only one, just show it normally.
            doc = getter_doc or setter_doc
            docstrings = [doc.splitlines()]
            for line in self.process_doc(docstrings):
                self.add_line(line, sourcename)

        # Add an rtype if requested.
        if self.env.config.autodoc_interrogatedb_add_rtype:
            itype = interrogate_element_type(self.ielem)
            if itype:
                type_name = self._format_type(itype)
                if type_name:
                    if interrogate_element_is_sequence(self.ielem):
                        line = ":rtype: Sequence[{0}]".format(type_name)
                    elif interrogate_element_is_mapping(self.ielem):
                        line = ":rtype: Mapping[{0}]".format(type_name)
                    else:
                        line = ":rtype: " + type_name
                    self.add_line('', sourcename)
                    self.add_line(line, sourcename)
                    self.add_line('', sourcename)
