#!/bin/python3

from tatsu import compile
from tatsu.util import asjsons
from pprint import pprint
import re


class SDL:

    def __init__(self, grammar, infile, outfile):

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
                for k, v in o.items():
                    if k == "comment":
                        # newline after comment
                        out.append(nl)
                    elif k in ("name", "type"):
                        # space around variable names
                        if out[-1] not in ('@', '[', '('):
                            out.append(' ')
                        if nth < len(ast)-1 and self.rew.match(ast[nth+1]):
                            v = v + ' '

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
                for oo in o:
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

    grammar = open("gram/graphql.ebnf").read()
    infile = "type.graphql"
    outfile = "gen/type.graphql"

    parser = SDL(grammar, infile, outfile)
    sdl = parser.stringify()

    print(sdl)
    #pprint(parser.ast, indent=2)
    ##asj = asjsons(ast)

    with open("u.graphql", 'w') as _f:
        _f.write(sdl)
