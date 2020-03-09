#!/bin/python3

'''Graphql format manipulation

Usage:
    ast.py [--debug] [FILE ...]

Parse the FILE input and apply transformations.
Options:
    -d --debug      Show debug informations.
'''

from tatsu import compile
from tatsu.util import asjsons
from pprint import pprint
import re
from docopt import docopt


class SDL:

    def __init__(self, grammar, infile):

        self.parser = compile(grammar)
        self.rew = re.compile(r'^\w+$')

        with open(infile) as _f:
            self.ast = self.parser.parse(_f.read(), parseinfo=False)

    def stringify(self, ast=None, out=None, root=False):

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
                    elif k in ("name", "type"):
                        # space around variable names
                        if out[-1] not in ('@', '[', '('):
                            out.append(' ')

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

                    if isinstance(oo, dict):
                        # space before 'implements'
                        if (mth < len(o)-1 and
                            all([k in ('name') for k in oo]) and
                            isinstance(o[mth+1], str) and
                            self.rew.match(o[mth+1])
                           ):
                            o[mth+1] = ' ' + o[mth+1]

                    out = self.stringify([oo], out)
            elif isinstance(o, str):
                if o == '{':
                    o = ' ' + o
                elif o == '}':
                    o = '\n'+o
                out.append(o)

        if root:
            out = ''.join(out)

        return out


if __name__ == "__main__":
    args = docopt(__doc__, version='0.0')

    grammar = open("gram/graphql.ebnf").read()
    if not args['FILE']:
        infile = "type.graphql"
    else:
        infile = args['FILE'][0]

    parser = SDL(grammar, infile)
    sdl = parser.stringify()

    print(sdl)

    if args['--debug']:
        #asj = asjsons(ast)
        pprint(parser.ast, indent=2)
