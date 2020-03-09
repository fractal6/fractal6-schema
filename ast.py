#!/bin/python3

'''Graphql format manipulation

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
from pprint import pprint
import re
from collections import defaultdict
from docopt import docopt

from gram.graphql import GRAPHQLParser


class GqlSemantics(object):
    def __init__(self):
        self.interfaces = defaultdict(list)

    def _default(self, ast):
        return ast

    def interface_type_definition(self, ast):
        if isinstance(ast, AST):
            # exists if there is a rulename defined
            interface = ast._name.name
            for o in ast._fields:
                if isinstance(o, list):
                    for oo in o:
                        if 'field' in oo:
                            self.interfaces[interface].append(oo)

        return ast

    def object_type_definition(self, ast):
        if isinstance(ast, AST):
            if ast._implements:
                for o in ast._implements:
                    # get the interface name
                    if isinstance(o, dict) and 'name' in o:
                        interface = o.name
                        fields = next(a for a in ast._fields if (isinstance(a, list)))
                        fields.extend(self.interfaces[interface])
                        break

        return ast


class SDL:

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

    def stringify(self, ast=None, out=None, root=False, _next=None):

        nl = '\n'

        if not ast:
            root = True
            ast = self.ast
            out = [nl]

        for nth, o in enumerate(ast):
            if isinstance(o, dict):
                # No Context here (nth == 0)
                for k, v in o.items():
                    if k == "comment":
                        # newline after comment
                        #out.append(nl)
                        # ignore comments
                        continue
                    elif v is None:
                        # empty choice (only happen with generated parser)
                        continue
                    elif k in ("name", "type"):
                        # space around variable names
                        if out[-1] not in ('@', '[', '('):
                            out.append(' ')
                            if isinstance(v, str):
                                if _next not in ('!', ':'):
                                    v += ' '
                    elif k.startswith('_'):
                        # Don't append newline for rulename that starts
                        # with '_'.
                        pass
                    elif k.endswith('_'):
                        # ignore keys taht ends with "_",
                        # They are used to postprocess the ast.
                        pass
                    elif k == 'directive':
                        # space before directive
                        out.append(' ')
                    elif k.endswith('_definition'):
                        # indention in field definition
                        out.extend([nl]*2)
                    else:
                        # newline rational
                        out.append(nl)

                    out = self.stringify([v], out)

            elif isinstance(o, list):
                # Assume Closure
                for mth, oo in enumerate(o):
                    if mth < len(o)-1:
                        _next = o[mth+1]
                    else:
                        _next = None
                    out = self.stringify([oo], out, _next=_next)
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
