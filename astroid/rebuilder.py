# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

"""this module contains utilities for rebuilding a ast tree in
order to get a single Astroid representation
"""

import ast
import collections
import sys

import astroid
from astroid import nodes

_BIN_OP_CLASSES = {
    ast.Add: '+',
    ast.BitAnd: '&',
    ast.BitOr: '|',
    ast.BitXor: '^',
    ast.Div: '/',
    ast.FloorDiv: '//',
    ast.Mod: '%',
    ast.Mult: '*',
    ast.Pow: '**',
    ast.Sub: '-',
    ast.LShift: '<<',
    ast.RShift: '>>',
}
if sys.version_info >= (3, 5):
    _BIN_OP_CLASSES[ast.MatMult] = '@'

_BOOL_OP_CLASSES = {ast.And: 'and', ast.Or: 'or', }

_UNARY_OP_CLASSES = {
    ast.UAdd: '+',
    ast.USub: '-',
    ast.Not: 'not',
    ast.Invert: '~',
}

_CMP_OP_CLASSES = {
    ast.Eq: '==',
    ast.Gt: '>',
    ast.GtE: '>=',
    ast.In: 'in',
    ast.Is: 'is',
    ast.IsNot: 'is not',
    ast.Lt: '<',
    ast.LtE: '<=',
    ast.NotEq: '!=',
    ast.NotIn: 'not in',
}

# Ellipsis is also one of these but has its own node
BUILTIN_NAMES = {
    'None': None,
    'NotImplemented': NotImplemented,
    'True': True,
    'False': False
}

REDIRECT = {
    'arguments': 'Arguments',
    'comprehension': 'Comprehension',
    "ListCompFor": 'Comprehension',
    "GenExprFor": 'Comprehension',
    'excepthandler': 'ExceptHandler',
    'keyword': 'Keyword',
}
PY3 = sys.version_info >= (3, 0)
PY34 = sys.version_info >= (3, 4)
CONTEXTS = {
    ast.Load: astroid.Load,
    ast.Store: astroid.Store,
    ast.Del: astroid.Del,
    ast.Param: astroid.Store
}


def _get_doc(node):
    try:
        if isinstance(node.body[0],
                      ast.Expr) and isinstance(node.body[0].value, ast.Str):
            doc = node.body[0].value.s
            node.body = node.body[1:]
            return node, doc
        else:
            return node, None
    except IndexError:
        return node, None


def _visit_or_empty(node, attr, visitor, visit='visit', **kws):
    """If the given node has an attribute, visits the attribute, and
    otherwise returns None.

    """
    value = getattr(node, attr, None)
    if value:
        return getattr(visitor, visit)(value, **kws)
    else:
        return nodes.Empty


def _get_context(node):
    return CONTEXTS.get(type(node.ctx), astroid.Load)


class ParameterVisitor(object):
    """A visitor which is used for building the components of Arguments node."""

    def __init__(self, visitor):
        self._visitor = visitor

    def visit(self, param_node, *args):
        cls_name = param_node.__class__.__name__
        visit_name = 'visit_' + REDIRECT.get(cls_name, cls_name).lower()
        visit_method = getattr(self, visit_name)
        return visit_method(param_node, *args)

    def visit_arg(self, param_node, *args):
        name = param_node.arg
        return self._build_parameter(param_node, name, *args)

    def visit_name(self, param_node, *args):
        name = param_node.id
        return self._build_parameter(param_node, name, *args)

    def visit_tuple(self, param_node, default):
        # We're not supporting nested arguments anymore, but in order to
        # simply not crash when running on Python 2, we're unpacking the elements
        # before hand. We simply don't want to support this feature anymore,
        # so it's possible to be broken.
        converted_node = self._visitor.visit(param_node)
        for element in converted_node.elts:
            param = nodes.Parameter(name=element.name,
                                    default=default,
                                    annotation=nodes.Empty,
                                    lineno=param_node.lineno,
                                    col_offset=param_node.col_offset)
            yield param

    def _build_parameter(self, param_node, name, default):
        annotation = nodes.Empty
        param_annotation = getattr(param_node, 'annotation', nodes.Empty)
        if param_annotation:
            annotation = self._visitor.visit(param_annotation)

        param = nodes.Parameter(
            name=name,
            default=default,
            annotation=annotation,
            lineno=getattr(param_node, 'lineno', None),
            col_offset=getattr(param_node, 'col_offset', None))
        yield param


class TreeRebuilder(object):
    """Rebuilds the ast tree to become an Astroid tree"""

    def __init__(self):
        self._global_names = []
        self._visit_meths = {}

    def visit_module(self, node, modname, modpath, package):
        """visit a Module node by returning a fresh instance of it"""
        node, doc = _get_doc(node)
        newnode = nodes.Module(name=modname,
                               doc=doc,
                               file_encoding='???',
                               package=package,
                               pure_python=True,
                               source_code='???',
                               source_file=modpath,
                               body=[self.visit(child) for child in node.body])
        return newnode

    def visit(self, node):
        cls = node.__class__
        if cls in self._visit_meths:
            visit_method = self._visit_meths[cls]
        else:
            cls_name = cls.__name__
            visit_name = 'visit_' + REDIRECT.get(cls_name, cls_name).lower()
            visit_method = getattr(self, visit_name)
            self._visit_meths[cls] = visit_method
        return visit_method(node)

    def visit_arguments(self, node):
        """visit a Arguments node by returning a fresh instance of it"""

        def _build_variadic(field_name):
            param = nodes.Empty
            variadic = getattr(node, field_name)

            if variadic:
                # Various places to get the name from.
                try:
                    param_name = variadic.id
                except AttributeError:
                    try:
                        param_name = variadic.arg
                    except AttributeError:
                        param_name = variadic

                # Get the annotation of the variadic node.
                annotation = nodes.Empty
                default = nodes.Empty
                variadic_annotation = getattr(variadic, 'annotation',
                                              nodes.Empty)
                if variadic_annotation is None:
                    # Support for Python 3.3.
                    variadic_annotation = getattr(
                        node, field_name + 'annotation', nodes.Empty)
                if variadic_annotation:
                    annotation = self.visit(variadic_annotation)

                lineno = getattr(variadic, 'lineno', None)
                col_offset = getattr(variadic, 'col_offset', None)
                param = nodes.Parameter(name=param_name,
                                        default=default,
                                        annotation=annotation,
                                        lineno=lineno,
                                        col_offset=col_offset)
            return param

        def _build_args(params, defaults):
            # Pad the list of defaults so that each arguments gets a default.
            defaults = collections.deque(defaults)
            while len(defaults) != len(params):
                defaults.appendleft(nodes.Empty)

            param_visitor = ParameterVisitor(self)
            for parameter in params:
                default = defaults.popleft()
                if default:
                    default = self.visit(default)

                for param in param_visitor.visit(parameter, default):
                    yield param

        # Build the arguments list.
        positional_args = list(_build_args(node.args, node.defaults))
        kwonlyargs = list(_build_args(getattr(node, 'kwonlyargs', ()),
                                      getattr(node, 'kw_defaults', ())))
        # Build vararg and kwarg.
        vararg = _build_variadic('vararg')
        kwarg = _build_variadic('kwarg')
        # Prepare the arguments new node.
        newnode = nodes.Arguments(args=positional_args,
                                  vararg=vararg,
                                  kwarg=kwarg,
                                  keyword_only=kwonlyargs,
                                  positional_only=[])
        return newnode

    def visit_assert(self, node):
        """visit a Assert node by returning a fresh instance of it"""
        if node.msg:
            msg = self.visit(node.msg)
        else:
            msg = nodes.Empty
        newnode = nodes.Assert(test=self.visit(node.test),
                               fail=msg,
                               lineno=node.lineno,
                               col_offset=node.col_offset)
        return newnode

    def visit_assign(self, node):
        """visit a Assign node by returning a fresh instance of it"""
        newnode = nodes.Assign(
            targets=[self.visit(child) for child in node.targets],
            value=self.visit(node.value),
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_assignname(self, node, node_name=None):
        '''visit a node and return a AssignName node'''
        newnode = nodes.AssignName(
            name=node_name,
            lineno=getattr(node, 'lineno', None),
            col_offset=getattr(node, 'col_offset', None))
        return newnode

    def visit_augassign(self, node):
        """visit a AugAssign node by returning a fresh instance of it"""
        newnode = nodes.AugAssign(op=_BIN_OP_CLASSES[type(node.op)] + "=",
                                  target=self.visit(node.target),
                                  value=self.visit(node.value),
                                  lineno=node.lineno,
                                  col_offset=node.col_offset)
        return newnode

    def visit_repr(self, node):
        """visit a Backquote node by returning a fresh instance of it"""
        newnode = nodes.Repr(value=self.visit(node.value),
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_binop(self, node):
        """visit a BinOp node by returning a fresh instance of it"""
        newnode = nodes.BinOp(op=_BIN_OP_CLASSES[type(node.op)],
                              left=self.visit(node.left),
                              right=self.visit(node.right),
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_boolop(self, node):
        """visit a BoolOp node by returning a fresh instance of it"""
        newnode = nodes.BoolOp(
            op=_BOOL_OP_CLASSES[type(node.op)],
            values=[self.visit(child) for child in node.values],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_break(self, node):
        """visit a Break node by returning a fresh instance of it"""
        return nodes.Break(lineno=getattr(node, 'lineno', None),
                           col_offset=getattr(node, 'col_offset', None))

    def visit_call(self, node):
        """visit a CallFunc node by returning a fresh instance of it"""
        starargs = _visit_or_empty(node, 'starargs', self)
        kwargs = _visit_or_empty(node, 'kwargs', self)
        args = [self.visit(child) for child in node.args]

        if node.keywords:
            keywords = [self.visit(child) for child in node.keywords]
        else:
            keywords = ()
        if starargs:
            new_starargs = nodes.Starred(value=starargs,
                                         ctx=starargs.col_offset,
                                         lineno=starargs.lineno)
            args.append(new_starargs)
        if kwargs:
            new_kwargs = nodes.Keyword(arg=None,
                                       value=kwargs,
                                       lineno=kwargs.col_offset,
                                       col_offset=kwargs.lineno)
            if keywords:
                keywords.append(new_kwargs)
            else:
                keywords = [new_kwargs]

        newnode = nodes.Call(func=self.visit(node.func),
                             args=args,
                             keywords=keywords,
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_classdef(self, node):  # , newstyle=None):
        """visit a ClassDef node to become astroid"""
        node, doc = _get_doc(node)
        if PY3:
            keywords = [self.visit_keyword(keyword)
                        for keyword in node.keywords]
        else:
            keywords = []
        if node.decorator_list:
            decorators = self.visit_decorators(node)
        else:
            decorators = []
        newnode = nodes.ClassDef(
            name=node.name,
            doc=doc,
            bases=[self.visit(child) for child in node.bases],
            body=[self.visit(child) for child in node.body],
            decorators=decorators,
            keywords=keywords,
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_const(self, node):
        """visit a Const node by returning a fresh instance of it"""
        return nodes.Const(value=node.value,
                           lineno=getattr(node, 'lineno', None),
                           col_offset=getattr(node, 'col_offset', None))

    def visit_continue(self, node):
        """visit a Continue node by returning a fresh instance of it"""
        return nodes.Continue(lineno=getattr(node, 'lineno', None),
                              col_offset=getattr(node, 'col_offset', None))

    def visit_compare(self, node):
        """visit a Compare node by returning a fresh instance of it"""
        newnode = nodes.Compare(
            ops=[_CMP_OP_CLASSES[type(op)] for op in node.ops],
            left=self.visit(node.left),
            comparators=[self.visit(expr) for expr in node.comparators],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_comprehension(self, node):
        """visit a Comprehension node by returning a fresh instance of it"""
        newnode = nodes.Comprehension(
            target=self.visit(node.target),
            iter=self.visit(node.iter),
            ifs=[self.visit(child) for child in node.ifs])
        return newnode

    def visit_decorators(self, node):
        """visit a Decorators node by returning a fresh instance of it"""
        # /!\ node is actually a ast.FunctionDef node while
        # parent is a astroid.nodes.FunctionDef node
        newnode = nodes.Decorators(
            nodes=[self.visit(child) for child in node.decorator_list],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_delete(self, node):
        """visit a Delete node by returning a fresh instance of it"""
        newnode = nodes.Delete(
            targets=[self.visit(child) for child in node.targets],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def _visit_dict_items(self, node):
        for key, value in zip(node.keys, node.values):
            rebuilt_value = self.visit(value)
            if not key:
                # Python 3.5 and extended unpacking
                rebuilt_key = nodes.DictUnpack(
                    lineno=rebuilt_value.lineno,
                    col_offset=rebuilt_value.col_offset)
            else:
                rebuilt_key = self.visit(key)
            yield rebuilt_key, rebuilt_value

    def visit_dict(self, node):
        """visit a Dict node by returning a fresh instance of it"""
        items = list(self._visit_dict_items(node))
        if items:
            keys, values = zip(*items)
        else:
            keys, values = [], []
        newnode = nodes.Dict(keys=keys,
                             values=values,
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_dictcomp(self, node):
        """visit a DictComp node by returning a fresh instance of it"""
        newnode = nodes.DictComp(
            generators=[self.visit(child) for child in node.generators],
            key=self.visit(node.key),
            value=self.visit(node.value),
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_expr(self, node):
        """visit a Expr node by returning a fresh instance of it"""
        newnode = nodes.Expr(value=self.visit(node.value),
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_ellipsis(self, node):
        """visit an Ellipsis node by returning a fresh instance of it"""
        return nodes.Ellipsis(lineno=getattr(node, 'lineno', None),
                              col_offset=getattr(node, 'col_offset', None))

    def visit_excepthandler(self, node):
        """visit an ExceptHandler node by returning a fresh instance of it"""
        # /!\ node.name can be a tuple
        newnode = nodes.ExceptHandler(
            type=_visit_or_empty(node, 'type', self),
            name=_visit_or_empty(node, 'name', self),
            body=[self.visit(child) for child in node.body],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_exec(self, node):
        """visit an Exec node by returning a fresh instance of it"""
        newnode = nodes.Exec(expr=self.visit(node.body),
                             globals=_visit_or_empty(node, 'globals', self),
                             locals=_visit_or_empty(node, 'locals', self),
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_extslice(self, node):
        """visit an ExtSlice node by returning a fresh instance of it"""
        newnode = nodes.ExtSlice(dims=[self.visit(dim) for dim in node.dims])
        return newnode

    def _visit_for(self, cls, node):
        """visit a For node by returning a fresh instance of it"""
        newnode = cls(target=self.visit(node.target),
                      iter=self.visit(node.iter),
                      body=[self.visit(child) for child in node.body],
                      orelse=[self.visit(child) for child in node.orelse],
                      lineno=node.lineno,
                      col_offset=node.col_offset)
        return newnode

    def visit_for(self, node):
        return self._visit_for(nodes.For, node)

    def visit_importfrom(self, node):
        """visit an ImportFrom node by returning a fresh instance of it"""
        names = [(alias.name, alias.asname) for alias in node.names]
        newnode = nodes.ImportFrom(
            modname=node.module or '',
            names=names,
            level=node.level or None,
            lineno=getattr(node, 'lineno', None),
            col_offset=getattr(node, 'col_offset', None))
        return newnode

    def _visit_functiondef(self, cls, node):
        """visit an FunctionDef node to become astroid"""
        self._global_names.append({})
        node, doc = _get_doc(node)
        if node.decorator_list:
            decorators = self.visit_decorators(node)
        else:
            decorators = nodes.Empty
        if PY3 and node.returns:
            returns = self.visit(node.returns)
        else:
            returns = nodes.Empty
        newnode = cls(name=node.name,
                      doc=doc,
                      args=self.visit(node.args),
                      body=[self.visit(child) for child in node.body],
                      decorators=decorators,
                      returns=returns,
                      lineno=node.lineno,
                      col_offset=node.col_offset)
        self._global_names.pop()
        return newnode

    def visit_functiondef(self, node):
        return self._visit_functiondef(nodes.FunctionDef, node)

    def visit_generatorexp(self, node):
        """visit a GeneratorExp node by returning a fresh instance of it"""
        newnode = nodes.GeneratorExp(
            generators=[self.visit(child) for child in node.generators],
            elt=self.visit(node.elt),
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_attribute(self, node):
        """visit an Attribute node by returning a fresh instance of it"""
        context = _get_context(node)
        # FIXME : maybe we should reintroduce and visit_delattr ?
        # for instance, deactivating assign_ctx
        if context == astroid.Del:
            newnode = nodes.DelAttr(attrname=node.attr,
                                    expr=self.visit(node.value),
                                    lineno=node.lineno,
                                    col_offset=node.col_offset)
        elif context == astroid.Store:
            newnode = nodes.AssignAttr(attrname=node.attr,
                                       expr=self.visit(node.value),
                                       lineno=node.lineno,
                                       col_offset=node.col_offset)
        else:
            newnode = nodes.Attribute(attrname=node.attr,
                                      expr=self.visit(node.value),
                                      lineno=node.lineno,
                                      col_offset=node.col_offset)
        return newnode

    def visit_global(self, node):
        """visit a Global node to become astroid"""
        newnode = nodes.Global(names=node.names,
                               lineno=getattr(node, 'lineno', None),
                               col_offset=getattr(node, 'col_offset', None))
        if self._global_names:  # global at the module level, no effect
            for name in node.names:
                self._global_names[-1].setdefault(name, []).append(newnode)
        return newnode

    def visit_if(self, node):
        """visit an If node by returning a fresh instance of it"""
        newnode = nodes.If(test=self.visit(node.test),
                           body=[self.visit(child) for child in node.body],
                           orelse=[self.visit(child) for child in node.orelse],
                           lineno=node.lineno,
                           col_offset=node.col_offset)
        return newnode

    def visit_ifexp(self, node):
        """visit a IfExp node by returning a fresh instance of it"""
        newnode = nodes.IfExp(test=self.visit(node.test),
                              body=self.visit(node.body),
                              orelse=self.visit(node.orelse),
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_import(self, node):
        """visit a Import node by returning a fresh instance of it"""
        names = [(alias.name, alias.asname) for alias in node.names]
        newnode = nodes.Import(names=names,
                               lineno=getattr(node, 'lineno', None),
                               col_offset=getattr(node, 'col_offset', None))
        return newnode

    def visit_index(self, node):
        """visit a Index node by returning a fresh instance of it"""
        newnode = nodes.Index(value=self.visit(node.value))
        return newnode

    def visit_keyword(self, node):
        """visit a Keyword node by returning a fresh instance of it"""
        newnode = nodes.Keyword(value=self.visit(node.value), arg=node.arg)
        return newnode

    def visit_lambda(self, node):
        """visit a Lambda node by returning a fresh instance of it"""
        newnode = nodes.Lambda(args=self.visit(node.args),
                               body=self.visit(node.body),
                               lineno=node.lineno,
                               col_offset=node.col_offset)
        return newnode

    def visit_list(self, node):
        """visit a List node by returning a fresh instance of it"""
        context = _get_context(node)
        newnode = nodes.List(ctx=context,
                             elts=[self.visit(child) for child in node.elts],
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_listcomp(self, node):
        """visit a ListComp node by returning a fresh instance of it"""
        newnode = nodes.ListComp(
            generators=[self.visit(child) for child in node.generators],
            elt=self.visit(node.elt),
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_name(self, node):
        """visit a Name node by returning a fresh instance of it"""
        context = _get_context(node)
        # True and False can be assigned to something in py2x, so we have to
        # check first the context.
        if context == astroid.Del:
            newnode = nodes.DelName(name=node.id,
                                    lineno=node.lineno,
                                    col_offset=node.col_offset)
        elif context == astroid.Store:
            newnode = nodes.AssignName(name=node.id,
                                       lineno=node.lineno,
                                       col_offset=node.col_offset)
        elif node.id in BUILTIN_NAMES:
            newnode = nodes.NameConstant(
                value=BUILTIN_NAMES[node.id],
                lineno=getattr(node, 'lineno', None),
                col_offset=getattr(node, 'col_offset', None))
            return newnode
        else:
            newnode = nodes.Name(name=node.id,
                                 lineno=node.lineno,
                                 col_offset=node.col_offset)
        return newnode

    def visit_str(self, node):
        """visit a String/Bytes node by returning a fresh instance of Const"""
        return nodes.Const(value=node.s,
                           lineno=getattr(node, 'lineno', None),
                           col_offset=getattr(node, 'col_offset', None))

    visit_bytes = visit_str

    def visit_num(self, node):
        """visit a Num node by returning a fresh instance of Const"""
        return nodes.Const(value=node.n,
                           lineno=getattr(node, 'lineno', None),
                           col_offset=getattr(node, 'col_offset', None))

    def visit_pass(self, node):
        """visit a Pass node by returning a fresh instance of it"""
        return nodes.Pass(lineno=node.lineno, col_offset=node.col_offset)

    def visit_print(self, node):
        """visit a Print node by returning a fresh instance of it"""
        newnode = nodes.Print(
            nl=node.nl,
            dest=_visit_or_empty(node, 'dest', self),
            values=[self.visit(child) for child in node.values],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_raise(self, node):
        """visit a Raise node by returning a fresh instance of it"""
        newnode = nodes.Raise(exc=_visit_or_empty(node, 'type', self),
                              cause=_visit_or_empty(node, 'inst', self),
                              traceback=_visit_or_empty(node, 'tback', self),
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_return(self, node):
        """visit a Return node by returning a fresh instance of it"""
        newnode = nodes.Return(value=_visit_or_empty(node, 'value', self),
                               lineno=node.lineno,
                               col_offset=node.col_offset)
        return newnode

    def visit_set(self, node):
        """visit a Set node by returning a fresh instance of it"""
        newnode = nodes.Set(elts=[self.visit(child) for child in node.elts],
                            lineno=node.lineno,
                            col_offset=node.col_offset)
        return newnode

    def visit_setcomp(self, node):
        """visit a SetComp node by returning a fresh instance of it"""
        newnode = nodes.SetComp(
            generators=[self.visit(child) for child in node.generators],
            elt=self.visit(node.elt),
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_slice(self, node):
        """visit a Slice node by returning a fresh instance of it"""
        newnode = nodes.Slice(lower=_visit_or_empty(node, 'lower', self),
                              upper=_visit_or_empty(node, 'upper', self),
                              step=_visit_or_empty(node, 'step', self))
        return newnode

    def visit_subscript(self, node):
        """visit a Subscript node by returning a fresh instance of it"""
        context = _get_context(node)
        newnode = nodes.Subscript(ctx=context,
                                  value=self.visit(node.value),
                                  slice=self.visit(node.slice),
                                  lineno=node.lineno,
                                  col_offset=node.col_offset)
        return newnode

    def visit_tryexcept(self, node):
        """visit a TryExcept node by returning a fresh instance of it"""
        newnode = nodes.TryExcept(
            body=[self.visit(child) for child in node.body],
            handlers=[self.visit(child) for child in node.handlers],
            orelse=[self.visit(child) for child in node.orelse],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_tryfinally(self, node):
        """visit a TryFinally node by returning a fresh instance of it"""
        newnode = nodes.TryFinally(
            body=[self.visit(child) for child in node.body],
            finalbody=[self.visit(n) for n in node.finalbody],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_tuple(self, node):
        """visit a Tuple node by returning a fresh instance of it"""
        context = _get_context(node)
        newnode = nodes.Tuple(ctx=context,
                              elts=[self.visit(child) for child in node.elts],
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_unaryop(self, node):
        """visit a UnaryOp node by returning a fresh instance of it"""
        newnode = nodes.UnaryOp(op=_UNARY_OP_CLASSES[node.op.__class__],
                                operand=self.visit(node.operand),
                                lineno=node.lineno,
                                col_offset=node.col_offset)
        return newnode

    def visit_while(self, node):
        """visit a While node by returning a fresh instance of it"""
        newnode = nodes.While(
            test=self.visit(node.test),
            body=[self.visit(child) for child in node.body],
            orelse=[self.visit(child) for child in node.orelse],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_with(self, node):
        context_expr = self.visit(node.context_expr)
        optional_vars = _visit_or_empty(node, 'optional_vars', self)
        with_item = nodes.WithItem(context_expr=context_expr,
                                   optional_vars=optional_vars,
                                   lineno=node.context_expr.lineno,
                                   col_offset=node.context_expr.col_offset)
        newnode = nodes.With(items=[with_item],
                             body=[self.visit(child) for child in node.body],
                             lineno=node.lineno,
                             col_offset=node.col_offset)
        return newnode

    def visit_yield(self, node):
        """visit a Yield node by returning a fresh instance of it"""
        newnode = nodes.Yield(value=_visit_or_empty(node, 'value', self),
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode


class TreeRebuilder3(TreeRebuilder):
    """extend and overwrite TreeRebuilder for python3k"""

    def visit_nameconstant(self, node):
        # in Python 3.4 we have NameConstant for True / False / None
        return nodes.NameConstant(value=node.value,
                                  lineno=getattr(node, 'lineno', None),
                                  col_offset=getattr(node, 'col_offset', None))

    def visit_excepthandler(self, node):
        """visit an ExceptHandler node by returning a fresh instance of it"""
        if node.name:
            name = self.visit_assignname(node, node.name)
        else:
            name = nodes.Empty
        newnode = nodes.ExceptHandler(
            type=_visit_or_empty(node, 'type', self),
            name=name,
            body=[self.visit(child) for child in node.body],
            lineno=node.lineno,
            col_offset=node.col_offset)
        return newnode

    def visit_nonlocal(self, node):
        """visit a Nonlocal node and return a new instance of it"""
        return nodes.Nonlocal(names=node.names,
                              lineno=getattr(node, 'lineno', None),
                              col_offset=getattr(node, 'col_offset', None))

    def visit_raise(self, node):
        """visit a Raise node by returning a fresh instance of it"""
        newnode = nodes.Raise(exc=_visit_or_empty(node, 'exc', self),
                              cause=_visit_or_empty(node, 'cause', self),
                              traceback=nodes.Empty,
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_starred(self, node):
        """visit a Starred node and return a new instance of it"""
        context = _get_context(node)
        newnode = nodes.Starred(ctx=context,
                                value=self.visit(node.value),
                                lineno=node.lineno,
                                col_offset=node.col_offset)
        return newnode

    def visit_try(self, node):
        # python 3.3 introduce a new Try node replacing
        # TryFinally/TryExcept nodes
        if node.finalbody:
            if node.handlers:
                body = [self.visit_tryexcept(node)]
            else:
                body = [self.visit(child) for child in node.body]
            newnode = nodes.TryFinally(
                body=body,
                finalbody=[self.visit(n) for n in node.finalbody],
                lineno=node.lineno,
                col_offset=node.col_offset)
            return newnode
        elif node.handlers:
            return self.visit_tryexcept(node)

    def visit_with(self, node, constructor=nodes.With):
        newnode = constructor(items=[self.visit(item) for item in node.items],
                              body=[self.visit(child) for child in node.body],
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_withitem(self, node):
        context_expr = self.visit(node.context_expr)
        optional_vars = _visit_or_empty(node, 'optional_vars', self)
        newnode = nodes.WithItem(context_expr=context_expr,
                                 optional_vars=optional_vars,
                                 lineno=node.context_expr.lineno,
                                 col_offset=node.context_expr.col_offset)
        return newnode

    def visit_yieldfrom(self, node):
        newnode = nodes.YieldFrom(value=_visit_or_empty(node, 'value', self),
                                  lineno=node.lineno,
                                  col_offset=node.col_offset)
        return newnode

    # Async structs added in Python 3.5
    def visit_asyncfunctiondef(self, node):
        return self._visit_functiondef(nodes.AsyncFunctionDef, node)

    def visit_asyncfor(self, node):
        return self._visit_for(nodes.AsyncFor, node)

    def visit_await(self, node):
        newnode = nodes.Await(value=self.visit(node.value),
                              lineno=node.lineno,
                              col_offset=node.col_offset)
        return newnode

    def visit_asyncwith(self, node):
        return self.visit_with(node, constructor=nodes.AsyncWith)


if sys.version_info >= (3, 0):
    TreeRebuilder = TreeRebuilder3
