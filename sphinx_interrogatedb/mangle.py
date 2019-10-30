"""Contains functions to mangle the function/type name in the way that
interrogate's python-native interface does unless -nomangle is specified."""


def mangle_function_name(name):
    if name.startswith("__"):
        return name

    new = ""
    for i in name.split("_"):
        if new == "":
            new += i
        elif i == "":
            pass
        elif len(i) == 1:
            new += i[0].upper()
        else:
            new += i[0].upper() + i[1:]
    return new


def mangle_type_name(name):
    # Equivalent to C++ classNameFromCppName
    class_name = ""
    bad_chars = "!@#$%^&*()<>,.-=+~{}? "
    next_cap = False
    first_char = True

    for chr in name:
        if (chr == '_' or chr == ' '):
            next_cap = True
        elif chr in bad_chars:
            class_name += '_'
        elif next_cap or first_char:
            class_name += chr.upper()
            next_cap = False
            first_char = False
        else:
            class_name += chr

    return class_name
