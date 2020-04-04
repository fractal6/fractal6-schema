#!/bin/python3

'''Graphql format manipulation

Remove comments.
Add interface attributes on implemented types.

Usage:
    ast.py [--debug] [--nv] [FILE ...]

Parse the FILE input and apply transformations.

Options:
    -d --debug      Show debug informations.
    --nv             silent
'''

from tatsu import compile
from tatsu.util import asjsons
from tatsu.ast import AST
import sys
import re
import itertools
from collections import OrderedDict, defaultdict
from pprint import pprint
from docopt import docopt

from gram.graphql import GRAPHQLParser

sys.setrecursionlimit(10**4)


class AST2(AST):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

    def clear(self):
        while len(self) > 0:
            self._clear()

    def _clear(self):
        for k in self:
            del self[k]


class SemanticFilter:

    def __init__(self):
        self.interfaces = OrderedDict()
        self.types = OrderedDict()
        self.inputs = OrderedDict()
        self.enums = []

    @staticmethod
    def get_name(ast):
        return ast._name.name

    @staticmethod
    def get_fields(ast):
        ''' Returns the fields of a object. '''
        # Assumes non empty type
        assert(len(ast._fields) == 3)
        fields = ast._fields[1]
        # ===
        #fields = next(a for a in ast._fields if (isinstance(a, list)))
        return fields

    @staticmethod
    def get_args(field):
        ''' field is an ast.
            Returns an ast representing the args
        '''

        if field.get('args'):
            assert(field.args[0] == '(')
            assert(field.args[-1] == ')')
            return field.args
        else:
            return None

    @staticmethod
    def _ast_set(ast, rule_name, value, pos=None):
        assert(isinstance(ast, AST))
        items = list(ast.items())
        if pos:
            # DEBUG AST, assumen empty rule are push at the end
            i = list(ast).index(rule_name)
            items.pop(i)
            assert(list(ast)[pos] != rule_name)
            assert(i > pos)
            items = items[:pos] + [(rule_name, value)] + items[pos:]

        ast.clear()

        for k, _v in items:
            v = _v
            if k == rule_name:
                v = value
            ast[k] = v

    def populate_data(self, data_type, name, ast, filter_directives=True):
        data = getattr(self, data_type)
        data[name] = []
        self._populate_data(data, name, ast, filter_directives=filter_directives)
        return

    def _populate_data(self, data, name, ast, filter_directives=True):
        ''' Populate data from ast parsing. '''

        fields = self.get_fields(ast)
        for f in fields:
            field = f.field
            if not field.get('_name'):
                # Comments
                continue

            # Add field
            fn = self.get_name(field)
            field_data = {'name': fn,
                          'ast': f,
                          'ast_copy': f.copy(),
                          'args': None, # list of AST
                          'directives': [], # list of structured AST
                         }

            # Add and filter arguments
            field_data['args'] = self.get_args(field)

            # Add and filter directives
            if field.get("_directives"):
                to_remove = []
                for i, d in enumerate(field._directives):
                    # build directive lookup
                    dn = self.get_name(d)
                    field_data['directives'].append({
                        'name': dn,
                        'ast': d,
                        'ast_cpy': d.copy(),
                    })
                    if dn.startswith('input_'):
                        to_remove.append(i)

                # filter directives
                for i in to_remove[::-1]:
                    if filter_directives:
                        field._directives.pop(i)

            data[name].append(field_data)
        return

    def inherit_interface(self, ast):

        # Inherits implemented interface
        if ast._implements:
            # get fields ast
            fields = self.get_fields(ast)
            if len(ast._implements) > 2:
                raise NotImplementedError("Review this code for multiple inheritance.")
            for o in ast._implements:
                if hasattr(o, 'name'):
                    interface_name = o.name
                    for itf_fd in self.interfaces[interface_name]:
                        fd = itf_fd['ast']
                        if fd not in fields:
                            fields.append(fd)

    def move_directives(self, name_in, data_types_in,
                        name_out, data_type_out,
                        directive_name):
        _fields = None
        for data_type in data_types_in:
            data_in = getattr(self, data_type)
            if name_in in data_in:
                _fields = data_in[name_in]
                break

        if not _fields:
            raise ValueError("Type `%s' unknown" % name_in)

        data_out = getattr(self, data_type_out)
        for f in data_out[name_out]:
            for _f in _fields:
                if f['name'] != _f['name']:
                    continue

                for d in _f['directives']:
                    dn = d['name']
                    if re.search(directive_name, dn):
                        if not f['ast'].field._directives:
                            self._ast_set(f['ast'].field, '_directives', [])

                        f['ast'].field['_directives'].append(d['ast'])
        return

    def update_args(self, data_type, name, ast):

        data = getattr(self, data_type)
        for f in data[name]:
            for _ff in self.get_fields(ast):
                args = f['args']
                _field = _ff.field

                if f['name'] != self.get_name(_field):
                    continue

                new_args = self.get_args(_field)
                if not args and new_args:
                    pos = list(_field).index('args')
                    self._ast_set(f['ast'].field, 'args', new_args, pos)
        return


class GqlSemantics(object):
    def __init__(self):
        self.sf = SemanticFilter()

    #
    # Util semantic
    #

    def _default(self, ast):
        if isinstance(ast, AST):
            ast = AST2(ast)
        return ast

    def CHARACTER(self, ast):
        ast = AST(_join=''.join(ast._join))
        return ast

    def int_value(self, ast):
        flatten = itertools.chain.from_iterable
        ast = AST(_join=''.join(flatten(ast._join)))
        return ast

    def float_value(self, ast):
        flatten = itertools.chain.from_iterable
        ast = AST(_join=''.join(flatten(ast._join)))
        return ast

    #
    # Graphql Semantic
    #

    def interface_type_definition(self, ast):
        ''' Interface handle
            * filter ou doublon
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.interfaces:
            self.sf.update_args('interfaces', name, ast)
            return None
        else:
            self.sf.populate_data('interfaces', name, ast)

        return ast

    def object_type_definition(self, ast):
        ''' Type handle
            * filter ou doublon
            * add implemented interfaces fields if not already presents
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.types:
            self.sf.update_args('types', name, ast)
            return None
        else:
            self.sf.populate_data('types', name, ast)
            self.sf.inherit_interface(ast)

        return ast

    def input_object_type_definition(self, ast):
        ''' Input handle
            * filter ou doublon
            * add filtered directive
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.inputs:
            return None
        else:
            self.sf.populate_data('inputs', name, ast, filter_directives=False)

        type_name = None
        if name.endswith('Patch'):
            type_name = re.match(r"(\w*)Patch", name).groups()[0]
        elif name.startswith('Add') and name.endswith('Input'):
            type_name = re.match(r"Add(\w*)Input", name).groups()[0]

        if type_name:
            self.sf.move_directives(type_name, ['types', 'interfaces'],
                                    name, 'inputs',
                                    r'^input_')
        return ast

    def enum_type_definition(self, ast):
        ''' Enum handle
            * filter ou doublon
        '''

        assert(not isinstance(ast, AST))

        name = ast[1].name
        # Watch out duplicate !
        if name in self.sf.enums:
            return None
        else:
            self.sf.enums.append(name)

        return ast


class SDL:
    ''' Parse graphql file with semantics.

        The module interpret the rule name given by tatsu
        (with the synxax `rule_name:rule`) with the following semantics:
            * if rule_name starts with "_", it will be appended to
                the output with no special treatment.
            * rule_name can be defined as `name__code` where code
              can be [ba, bb, bs] that stands respectively for:
                * blank after
                * blank before
                * blank surrounded
            * `name` has a special treatment to manage space syntax.
            * `comment` are filtered out.
            * `args` do not make new line.
            * other rule are appended with a new line,
              specially the `field` rule name.

        Furthermore special rule are defined be Semantic class `GqlSemantics`.
        Reports to the methods documentation for further informantion.
    '''

    def __init__(self, grammar, infile):
        self._grammar = open("gram/graphql.ebnf").read()
        self._target = open(infile).read()

        self.semantics = GqlSemantics()
        self.rew = re.compile(r'^\w+$')

        #self.parser = compile(self._grammar)
        self.parser = GRAPHQLParser()

        self.ast = self.parser.parse(self._target,
                                     rule_name="document",
                                     semantics=self.semantics,
                                     parseinfo=False)

        self.sf = self.semantics.sf

    def stringify(self, ast=None, out=None, root=False,
                  _prev=None, _next=None, ignore_nl=False):

        nl = '\n'

        if ast is None:
            root = True
            ast = self.ast
            out = [nl]

        for nth, o in enumerate(ast):
            if isinstance(o, AST):
                keys = list(o)
                update = False
                if len(keys) != len(set(keys)):
                    # @DEBUG: duplicate keys in AST (caused by AST updates!)
                    raise ValueError('Related to tatsu.AST issue #164..')

                if len(keys) > 1:
                    update = True

                for ith, k in enumerate(keys):
                    pack = k.split('__')
                    v = o[k]

                    if len(pack) == 2:
                        _type, code = pack
                    else:
                        _type = k
                        code = None

                    if update:
                        if ith > 0:
                            _prev = o[keys[ith-1]]
                        if ith < len(o) - 1:
                            _next = o[keys[ith+1]]

                    # Code filtering
                    if code == 'bb':
                        # Blank Before (space)
                        if out[-1] != ' ':
                            out.append(' ')
                    elif code == 'ba':
                        # Blank After (space)
                        v += ' '
                    elif code == 'bs':
                        # Blank Suround (space)
                        if isinstance(v, str):
                            if out[-1] == ' ':
                                v += ' '
                            else:
                                v = ' ' + v + ' '

                    if v is None:
                        # empty choice (only happen with generated parser)
                        continue

                    # type/rule_name filtering
                    if _type in "comment":
                        # ignore comments
                        continue
                    elif _type == "args":
                        ignore_nl = True
                    elif _type in ("name"):
                        # Manage space btween names

                        if out[-1] == '\n':
                            # field indentation
                            if _prev in ('{',) and out[-3][-1] != ' ':
                                out[-3] += ' '
                            out.append('  ')
                        elif out[-1] not in ('[', '(', '@'):
                            # Space separator between words.
                            out.append(' ')
                        elif _prev in ("[",):
                            out[-2] += ' '

                        # space after object definition
                        if _next and _next == '{':
                            # without AST
                            v += ' '
                        elif _next and isinstance(_next, list) and _next[0] == '{':
                            # with AST
                            v += ' '
                        elif _next and isinstance(_next, list) and _next[0] == 'implements':
                            v += ' '

                        #print("dict-- ", k, v, _prev, _next)

                    elif _type.startswith('_'):
                        # Don't append newline for rulename that starts with '_'.
                        pass
                    elif _type.endswith('_definition'):
                        # indention in field definition
                        out.extend([nl]*2)
                    else:
                        # newline rational
                        if not ignore_nl:
                            out.append(nl)

                    out = self.stringify([v], # removing list breaks the space logics
                                         out,
                                         _prev=_prev, _next=_next,
                                         ignore_nl=ignore_nl,
                               )

            elif isinstance(o, list):
                # Assume Closure
                for mth, oo in enumerate(o):
                    if mth < len(o)-1:
                        _next = o[mth+1]

                    if mth > 0:
                        _prev = o[mth-1]

                    out = self.stringify([oo], # removing list breaks the space logics
                                         out,
                                         _prev=_prev, _next=_next,
                                         ignore_nl=ignore_nl)
            elif isinstance(o, str):
                if o == '}':
                    o = '\n'+o
                out.append(o)
            else:
                raise NotImplementedError("Unknown type: %s" % type(o))

        if root:
            out = ''.join(out)

        return out


if __name__ == "__main__":
    args = docopt(__doc__, version='0.0')

    grammar = 'gram/graphql.ebnf'
    if not args['FILE']:
        infile = "type.graphql"
    else:
        infile = args['FILE'][0]

    parser = SDL(grammar, infile)
    sdl = parser.stringify()

    if not args['--nv']:
        print(sdl)

    if args['--debug']:
        #asj = asjsons(ast)
        pprint(parser.ast, indent=2)
