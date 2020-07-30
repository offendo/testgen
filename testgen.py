#!/usr/bin/env python3.8

import os
import textwrap
from pathlib import Path
import sys
import importlib
import inspect
import colorama

colorama.init()
from colorama import Fore, Back, Style


#   +--------------------------------------------------+
#   |                    UTILITIES                     |
#   +--------------------------------------------------+


def _build_tree(root, get_children, make_key, ignore_if):
    """ Builds a tree given a root node, a way to get children, and a way to make keys

    Args:
        root: the (current) root node for the tree
        get_children: a function to get the child nodes of root
        make_key: a function to make a key out of the root node
        ignore_if: (optional) a filter function

    Returns:
        A recursively generated tree of {make_key(root): get_children(root)}
    """
    result = {}
    children = get_children(root)
    # if there are no children, just return the root (leaf)
    if not children:
        return root
    # otherwise, keep going down
    for item in children:
        if ignore_if(item):
            continue
        result[make_key(item)] = _build_tree(
            root=item, get_children=get_children, make_key=make_key, ignore_if=ignore_if
        )
    return result


def is_submodule(child, parent):
    """ Returns True if child is a submodule of parent

    Args:
        child: the child module in question 
        parent: the parent module in question 

    Returns:
        True if child < parent, False otherwise
    """
    if not hasattr(parent, "__path__"):
        return False
    if hasattr(child, "__path__"):
        parentpath = parent.__path__[0]
        childpath = child.__path__[0]
        return childpath.startswith(parentpath)
    elif hasattr(child, "__file__"):
        parentpath = parent.__path__[0]
        childpath = child.__file__
        return childpath.startswith(parentpath)
    return False


def get_testables(obj, ignore=None):
    """ Gets all member functions and classes of obj (module, class, or function)
    
    Args:
        obj: object to parse
        ignore: members to ignore

    Returns:
        List of testables (functions, classes, or methods) belonging to obj
    """
    ignore = set(ignore) if ignore else {}
    is_testable = lambda x: (is_subfunction(x, obj) or is_subclass(x, obj))
    testables = inspect.getmembers(obj, predicate=is_testable)
    return [v for k, v in testables if k not in ignore]


def get_submodules(module, ignore):
    """ Gets a list of submodules for a given module

    Args:
        module: Module object
        ignore (list): list of modules to ignore when writing tests
    Returns:
        List of submodules for module
    """
    # get all submodules
    members = inspect.getmembers(module)
    members = inspect.getmembers(module, predicate=lambda x: is_submodule(x, module))
    # get rid of anything that's in ignore and return
    submodules = [v for k, v in filter(lambda x: x[1].__name__ not in ignore, members)]
    return submodules


def get_submodule_tree(root, ignore=None):
    """ Builds a tree of submodules starting with given root

    Args:
        root: the root module to parse
        ignore: a list of modules to ignore(in form 'root.sub1.sub2....')
    Returns:
        dictionary in tree form of all submodules, with key as the module name and value as the
            module objects (at the leaf level)

    """
    ignore = set(ignore) if ignore else {}
    get_children = lambda x: get_submodules(x, ignore)
    ignore_if = lambda x: x.__name__ in ignore
    make_key = lambda x: x.__name__
    return _build_tree(
        root, get_children=get_children, make_key=make_key, ignore_if=ignore_if
    )


def is_subfunction(obj, parent):
    """ Returns true if obj is a function or method

    Args:
        obj: object in question

    Returns:
        True if obj is a function or method and a member of parent
    """
    if inspect.isclass(parent):
        return (
            inspect.isfunction(obj) or inspect.ismethod(obj)
        ) and obj.__module__ == parent.__module__
    if inspect.ismodule(parent):
        return (
            inspect.isfunction(obj) or inspect.ismethod(obj)
        ) and obj.__module__ == parent.__name__
    return False


def is_subclass(obj, parent):
    """ Returns true if obj is a function or method

    Args:
        obj: object in question

    Returns:
        True if obj is a class and a member of parent
    """
    if inspect.isclass(parent):
        return inspect.isclass(obj) and obj.__module__ == parent.__module__
    if inspect.ismodule(parent):
        return inspect.isclass(obj) and obj.__module__ == parent.__name__
    return False


def indent(text, n, spaces=4):
    """ Indents text with spaces n times
    Args:
        text: the text to indent
        n: the number of times to indent
        spaces: how many spaces to use per indentation
    Returns:
        indented text
    """
    return textwrap.indent(text, " " * n * spaces)


def get_function_test_name(func):
    name = func.__name__
    return f"test_{name}"


def get_class_test_name(cls):
    name = cls.__name__
    return f"Test{name}"


def exists_test(obj, context):
    """ Given an object and a list of members (context), determine if the test for obj exists
    """
    if inspect.isclass(obj):
        name = get_class_test_name(obj)
    elif inspect.isfunction(obj):
        name = get_function_test_name(obj)
    elif inspect.ismethod(obj):
        name = get_function_test_name(obj)
    for item in context:
        if item.__name__ == name:
            return item
    return False


#   +--------------------------------------------------+
#   |                       MAIN                       |
#   +--------------------------------------------------+


def _help_setup_files(base, modules):
    """ Helper function for `setup_files`
    """
    result = []
    if not isinstance(modules, dict):
        modules = {modules.__name__: modules}
    for name, submod in modules.items():
        # if the module is a directory, make the test directory
        if isinstance(submod, dict):
            # e.g. preprocess.script
            subpath = base / "/".join(name.split(".")[1:])
            subpath.mkdir(exist_ok=True, parents=True)
            # print(subpath)
            result.extend(_help_setup_files(base, submod))
        else:  # otherwise, create a file and append it to the list
            filename = "test_" + name.split(".")[-1] + ".py"
            fullpath = base / "/".join(name.split(".")[1:-1]) / filename
            fullpath.parent.mkdir(exist_ok=True, parents=True)

            os.chdir(base.parent)
            testmod = (
                f"{base.stem}." + ".".join(name.split(".")[1:-1]) + f".{filename[:-3]}"
            )

            if not fullpath.exists():
                with open(fullpath, "a") as f:
                    items = ",".join([v.__name__ for v in get_testables(submod)])
                    if items:
                        import_name = f"from {name} import {items}\n"
                    else:
                        import_name = f"import {name}\n"
                    import_pytest = "import pytest\n"
                    f.writelines([import_name, import_pytest])
            result.append((fullpath, submod, testmod))
    return result


def setup_files(path, modules):
    """ Builds and populates the test directory

    Args:
        path (str): The name/path of the test directory
        modules (dict): A tree (dictionary) of 'module_name: {submodule_1: {...}} to write tests for. The
            leaves (i.e., single files) should be {module_name: <module object>}
    Returns:
        List of (module, test_file, testmodule) for each leaf module in modules
    """
    base = Path(path)
    base.mkdir(exist_ok=True, parents=True)
    return _help_setup_files(base, modules)


def format_function(function, is_method=False):
    """ Formats the corresponding test function into a string

    Args:
        function: Function object to create test for
        is_method: If true, will add 'self' as an argument

    Returns:
        None
    """
    name = get_function_test_name(function)
    self = "self" if is_method else ""
    body = f"@pytest.mark.skip\n" f"def {name}({self}):\n" f"    pass\n"

    return body


def format_class(cls, n=1, exists=None):
    name = get_class_test_name(cls)
    # if there are any functions that exist, the class exists too so don't write again
    exists = set(exists) if exists else {}
    if exists:
        body = ""
    else:
        body = f"@pytest.mark.skip\n" f"class {name}:\n" f"    '''\n" f"    '''\n"
    for member in get_testables(cls, ["__init__"]):
        if is_subfunction(member, cls):
            # ignore the ones that already exist
            if exists_test(member, exists):
                continue
            body += indent(format_function(member, is_method=True), n=n, spaces=4)
        if is_subclass(member, cls):
            exists_in_subcls = get_testables(member, ["__init__"])
            if not exists_in_subcls:
                exists_in_subcls = [member]  # just so it's not empty
            body += indent(format_class(member, exists=exists_in_subcls), n=n, spaces=4)
    return body


def format_member(obj, exists):
    """ Formats either function or class to file pointer fp

    Args:
        obj: object to write
        fp: file object to write to
    Returns:
        Formatted member
    """
    if inspect.isfunction(obj) and (get_function_test_name(obj.__name__) not in exists):
        return format_function(obj, is_method=inspect.ismethod(obj))
    if inspect.isclass(obj):
        return format_class(obj, exists=exists)
    return ""


def generate_tests(mods):
    """ Given a list of (filepath, module), writes empty tests for each module

    Args:
        mods: a list of (filepath, module)

    Returns:
        None
    """
    for path, mod, testmod in mods:
        # have to check if the function/class exists already
        test_mod = importlib.import_module(testmod)
        exists = get_testables(test_mod)
        members = get_testables(mod)
        with open(path, "a") as f:
            for obj in members:
                # only write the function if it doesn't exist already
                if inspect.isfunction(obj):
                    if exists_test(obj, exists):
                        continue
                    body = format_function(obj, is_method=inspect.ismethod(obj))
                    f.write(body + "\n")
                # if it's a class, we may want to write the methods, so we have to determine later
                elif inspect.isclass(obj):
                    test_obj = exists_test(obj, exists)
                    if test_obj:
                        exists_in_cls = get_testables(test_obj)
                        existing_items = [
                            exists_test(i, exists_in_cls) for i in members
                        ]
                        existing_items = list(filter(None, existing_items))
                        if not exists_in_cls:
                            # the class exists, so just put an object here so it's not empty
                            exists_in_cls = [obj]
                        body = format_class(obj, exists=exists_in_cls)
                    else:
                        body = format_class(obj, exists=None)
                    f.write(body + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            Fore.WHITE
            + Style.BRIGHT
            + "\nTestGen: Generate unit tests for a python project\n"
            + Style.RESET_ALL
        )
        print(
            Fore.WHITE
            + "  >>> ./testgen "
            + Fore.BLUE
            + "<module> "
            + Fore.RED
            + "<output> "
        )
    else:
        mod = sys.argv[-2]
        mod = importlib.import_module(mod)
        modules = get_submodule_tree(mod)
        mods = setup_files(sys.argv[-1], modules)
        generate_tests(mods)
