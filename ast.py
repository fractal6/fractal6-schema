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
from collections import OrderedDict, defaultdict
from pprint import pprint
import re
from docopt import docopt

from gram.graphql import GRAPHQLParser


def populate_type_data(ast, data, type_name):
    ''' Populate data from ast parsing. '''

    # Assumes non empty type
    assert(len(ast._fields) == 3)
    fields = ast._fields[1]
    # ===
    #fields = next(a for a in ast._fields if (isinstance(a, list)))

    for f in fields:
        field = f.field
        if not field.get('_name'):
            # Comments
            continue

        # Add field
        field_data = {'name': field._name.name,
                      'ast': f,
                      'data': f.copy(),
                      'directives': [],
                     }

        if field.get("_directives"):
            # Add and filter directives
            for d in field._directives:
                # build directive lookup
                field_data['directives'].append({
                    'name': d._name.name,
                    'ast': d,
                    'data': d.copy(),
                })

        data[type_name].append(field_data)


class GqlSemantics(object):
    def __init__(self):
        self.interfaces = OrderedDict()
        self.types = OrderedDict()
        self.enums = []

    #
    # Util semantic
    #

    def _default(self, ast):
        return ast

    def CHARACTER(self, ast):
        ast = AST(_string=''.join(ast._string))
        return ast

    #
    # Graphql Semantic
    #

    def interface_type_definition(self, ast):
        ''' Interface handle
            * filter ou doublon
            * add interfaces to inner variables
        '''

        if not isinstance(ast, AST):
            return ast

        name = ast._name.name
        # Watch out duplicate !
        if name in self.interfaces:
            return None
        else:
            self.interfaces[name] = []

        populate_type_data(ast, self.interfaces, name)

        return ast

    def object_type_definition(self, ast):
        ''' Type handle
            * filter ou doublon
            * add implemented interfaces fields if not already presents
        '''
        if not isinstance(ast, AST):
            return ast

        name = ast._name.name
        # Watch out duplicate !
        if name in self.types:
            return None
        else:
            self.types[name] = []

        populate_type_data(ast, self.types, name)

        # Inherits implemteted interface
        if ast._implements:
            # get fields ast
            fields = next(a for a in ast._fields if (isinstance(a, list)))
            if len(ast._implements) > 2:
                raise NotImplementedError("Review this code for multiple inheritance.")
            for o in ast._implements:
                if hasattr(o, 'name'):
                    interface_name = o.name
                    for itf_fd in self.interfaces[interface_name]:
                        fd = itf_fd['ast']
                        if fd not in fields:
                            fields.append(fd)

        return ast

    def enum_type_definition(self, ast):
        ''' Enum handle
            * filter ou doublon
        '''

        if isinstance(ast, AST):
            raise NotImplementedError("Review this code if we got an AST here !")

        name = ast[1].name
        # Watch out duplicate !
        if name in self.enums:
            return None
        else:
            self.enums.append(name)

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

    def stringify(self, ast=None, out=None, root=False, _prev=None, _next=None, ignore_nl=False):

        nl = '\n'

        if not ast:
            root = True
            ast = self.ast
            out = [nl]

        for nth, o in enumerate(ast):
            if isinstance(o, dict):
                keys = list(o)
                update = False
                if len(keys) > 1:
                    update = True
                for ith, k in enumerate(keys):
                    code = None
                    pack = k.split('__')
                    if len(pack) == 2:
                        _type, code = pack
                    else:
                        _type = k
                    v = o[k]

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

                    # type/rule_name filtering
                    if _type in "comment":
                        # ignore comments
                        continue
                    elif v is None:
                        # empty choice (only happen with generated parser)
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
                        if _next == '{':
                            # without AST
                            v += ' '
                        elif isinstance(_next, list) and _next[0] == '{':
                            # with AST
                            v += ' '
                        elif isinstance(_next, list) and _next[0] == 'implements':
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

                    out = self.stringify([v], out, ignore_nl=ignore_nl, _prev=_prev, _next=_next)

            elif isinstance(o, list):
                # Assume Closure
                for mth, oo in enumerate(o):
                    if mth < len(o)-1:
                        _next = o[mth+1]

                    if mth > 0:
                        _prev = o[mth-1]
                    out = self.stringify([oo], out, _prev=_prev, _next=_next, ignore_nl=ignore_nl)
            elif isinstance(o, str):
                if o == '}':
                    o = '\n'+o
                out.append(o)

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
