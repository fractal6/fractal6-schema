#!/bin/python3

'''Graphql format manipulation

Usage:
    gqlast.py [--debug] [--dgraph] [--nv] [FILE ...]

Parse the FILE input and apply transformations:
* Add interface attributes on implemented types.
* remove duplicate type and inherits input arguments.
* move/copy directives based on their name (see graphql/directives.graphql).
* Remove comments.


Options:
    -d --debug      Show debug informations.
    ---dgraph       Filter schema for dgraph.
    --nv            Silent output.
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
        for k in list(self):
            del self[k]


class SemanticFilter:
    def __init__(self):
        self.interfaces = OrderedDict()
        self.types = OrderedDict()
        self.inputs = OrderedDict()
        self.enums = []

    @staticmethod
    def get_name(ast):
        if not ast:
            return ""
        else:
            return ast._name.name

    @staticmethod
    def get_fields(ast):
        ''' Returns the fields of a object.
            * remove comments
        '''
        assert(len(ast._fields) == 3)
        fields = ast._fields[1]
        # ===
        #fields = next(a for a in ast._fields if (isinstance(a, list)))

        # Filter Comments
        to_remove = [i for i, f in enumerate(fields) if not f.field.get('_name')]
        for i in to_remove[::-1]:
            fields.pop(i)

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

    @classmethod
    def get_directives(cls, field):
        ''' field is an ast.
            Returns an ast representing the directives
        '''

        if field.get('_directives'):
            return field._directives
        else:
            cls._ast_set(field, '_directives', [])
            return field._directives

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
        # LOG DEBUG
        #print("Populate: %s %s" % (data_type, name))
        data = getattr(self, data_type)
        data[name] = []
        self._populate_data(data, name, ast, filter_directives=filter_directives)
        return

    def _populate_data(self, data, name, ast, filter_directives=True):
        ''' Populate data from ast parsing. '''

        # Populate Types Directives
        data[name+"__directives"] = []
        if ast.get('_directives'):
            to_remove = []
            for i, d in enumerate(ast._directives):
                if not d:
                    continue

                data[name+"__directives"].append(d)
                if d._name.name == 'hook_':
                    to_remove.append(i)

            for i in to_remove[::-1]:
                ast._directives.pop(i)

        # add interfaces info
        if ast.get("_implements"):
            data[name+"__implements"] = ast._implements[1].name

        # Populate fields
        fields = self.get_fields(ast)
        for f in fields:
            self._push_field(name, f, data, filter_directives)

        return
    def _push_field(self, name, f, data, filter_directives=False, force=False):
        field = f.field

        # Add field
        fn = self.get_name(field)
        field_data = {'name': fn,
                      'ast': f,
                      #'ast_copy': f.copy(),
                      'args': None, # list of AST
                      'directives': [], # list of structured AST
                     }

        # Add and filter arguments
        field_data['args'] = self.get_args(field)

        # Add and filter directives
        if field.get("_directives"):
            to_remove = []
            for i, d in enumerate(field._directives):
                if not d:
                    continue

                # build directive lookup
                dn = self.get_name(d)
                field_data['directives'].append({
                    'name': dn,
                    'ast': d,
                    #'ast_copy': d.copy(),
                })
                if dn.startswith('x_') or dn.startswith('w_'):
                #if dn.startswith('add_') or dn.startswith('patch_') or dn.startswith('alter_'):
                    to_remove.append(i)

            # filter directives
            if filter_directives:
                for i in to_remove[::-1]:
                    field._directives.pop(i)

        if force:
            try:
                data[name][-1]['ast']["extra"] = f
            except:
                print(data[name][-1])
                exit()
        else:
            data[name].append(field_data)

        return field_data

    def inherit_interface(self, ast):
        '''Inherits implemented interface '''

        if not ast._implements:
            return

        if len(ast._implements) > 2:
            # @debug: multiple inheritance will break.
            raise NotImplementedError("Review this code for multiple inheritance.")
        else:
            interface_name = ast._implements[1].name

        # LOG DEBUG
        #print("%s Inheriting interface %s : " % (ast._name.name,  interface_name))
        #pprint(self.interfaces[interface_name])

        # Get ast fields...
        fields = self.get_fields(ast)
        field_names = [self.get_name(f.field) for f in fields]
        for itf_fd in self.interfaces[interface_name]:
            fd = itf_fd['ast']
            name = self.get_name(fd.field)
            if name in field_names:
                continue

            # LOG DEBUG
            #print("%s inherited %s field from %s" % (ast._name.name, name, interface_name))

            # Inherit a  field
            fields.append(fd)

            # Current field
            curfd = [x.field for x in fields if name == self.get_name(x.field)][0]

            # Inherit a directive
            directives = itf_fd["directives"]
            if not curfd._directives and directives:
                self._ast_set(curfd, '_directives',[x['ast'] for x in  directives])
                # LOG DEBUG
                #print("%s inherited %s directive from %s" % (curfd._name.name, len(directives), interface_name))


        return

    def inherit_interface_dgraph(self, ast):
        '''Inherits implemented interface.
            * if field is already defined in interface, removed it.
            * If type if empty add a dummy field.
        '''

        if not ast._implements:
            return

        if len(ast._implements) > 2:
            raise NotImplementedError("Review this code for multiple inheritance.")
        else:
            interface_name = ast._implements[1].name

        # Get ast fields
        fields = self.get_fields(ast)
        fd_names = [self.get_name(f['ast'].field) for f in self.interfaces[interface_name]]
        to_remove = []
        for i, f in enumerate(fields):
            if self.get_name(f.field) in fd_names:
                to_remove.append(i)

        for i in to_remove[::-1]:
            fields.pop(i)

        if len(fields) == 0:
            fields.append(AST(field="_VOID: String"))

        return

    def copy_directives(self, name_in, data_types_in,
                        name_out, data_type_out,
                        directive_name, set_default=False):
        _fields = None
        for data_type in data_types_in:
            data_in = getattr(self, data_type)
            if name_in in data_in:
                _fields = data_in[name_in]
                # LOG DEBUG
                #print("Entering input copy %s -> %s " % (name_in, name_out))
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
                        # LOG DEBUG
                        #print("directives %s  copied in %s" % (d["ast"]._name.name, name_out+"."+self.get_name(f['ast'].field)))

                if set_default and not f['ast'].field._directives:
                    # Protect the object from Patch queries by default...
                    ro = AST2({'_cst__bb': '@', '_name': AST2({'name': 'x_patch_ro'}), '_args': None})
                    self._ast_set(f['ast'].field, '_directives', [ro])

        return

    def copy_hook_directives(self, data_types_in, name_out, data_type_out):
        ''' Copy Special directive as pre and post hook that start by hook_*
            in mutation corresponding types. '''

        for data_type in data_types_in:
            data_in = getattr(self, data_type)
            data_out = getattr(self, data_type_out)
            for f in data_out[name_out]:
                #m = re.match(r"(add|update|delete|query|get)(\w*)", f['name'])
                m = re.match(r"(query|get|add|update|delete)(\w*)", f['name'])
                if not m:
                    # unnkow query
                    continue
                groups = m.groups()
                op = groups[0]
                type_ = groups[1]
                if type_ in data_in:
                    for directive_ in data_in[type_ + '__directives']:
                        if directive_._name.name != 'hook_':
                            continue
                        pre_directive = directive_.copy()
                        post_directive = directive_.copy()

                        # Add Pre Hook (Input) (Query + Mutations)
                        pre_directive["cst"] = op + type_ + "Input"
                        args = self.get_args(f['ast'].field)
                        args.insert(len(args)-1, pre_directive)

                        # Only add Post Hook for Mutation queries
                        if op in ("add", "update", "delete"):
                            # Add Post Hook (Query or Mutation Field)
                            post_directive["cst"] = op + type_
                            post_directives = self.get_directives(f['ast'].field)
                            post_directives.insert(len(post_directives)-1, post_directive)

    def update_fields(self, data_type, name, ast):
        ''' Add new fields if not present on object.
            Update arguments eventually.
        '''
        data = getattr(self, data_type)
        field_names = [x.get('name') for x in data[name]]
        interface_name = data.get(name+"__implements")
        if interface_name:
            field_names += [x.get('name') for x in getattr(self, "interfaces")[interface_name]]

        # LOG DEBUG
        #print("Updating Doublon: %s interface: %s, fields: %s" % (name, interface_name, field_names))
        for f in data[name]:
            # Iterates over the fields of the "duplicated" object <f>
            for _ff in self.get_fields(ast):
                _field = _ff.field
                _name = self.get_name(_field)

                if _name not in field_names and _name not in ['_VOID']:
                    # Add a new field.
                    self._push_field(name, _ff, data, force=True)
                    field_names.append(_name)

                elif f['name'] != _name:
                    #print(_name, self.get_args(_field))
                    #print(f['ast'].field)
                    #print("_-_-_-_-_-_-_")
                    continue
                else:
                    # Update args(input/filter); if the arguments don't already exists
                    # and if the  new field has non empty arguments.
                    args = f['args']
                    new_args = self.get_args(_field)
                    if not args and new_args:
                        pos = list(_field).index('args')
                        self._ast_set(f['ast'].field, 'args', new_args, pos)
        return


class GraphqlSemantics:

    ''' Base GQL semantic'''

    def __init__(self):
        self.sf = SemanticFilter()

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


class GqlgenSemantics(GraphqlSemantics):

    '''Gqlgen Semantic'''

    def interface_type_definition(self, ast):
        ''' Interface handle
            * filter ou doublon
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.interfaces:
            self.sf.update_fields('interfaces', name, ast)
            return None
        else:
            self.sf.populate_data('interfaces', name, ast)

        # rename interface to type for gqlgen compatibility !
        self.sf._ast_set(ast, '_cst', 'type')

        return ast

    def object_type_definition(self, ast):
        ''' Type handle
        * add or updated (doublon) types: Doublon occurs because Type are present twice, once from the file
             where the type is defined, and twice from the generated schema from dgraph.
             We need both because, the original bring the magixc query and input directive
             while Dgraph can bring new properties.
        * inherit from interfaces fields and directives if not already presents
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.types:
            self.sf.update_fields('types', name, ast)
            return None
        else:
            self.sf.inherit_interface(ast)
            self.sf.populate_data('types', name, ast)

        # remove interface gqlgen compatibility !
        self.sf._ast_set(ast, '_implements', None)

        if name in ("Mutation", "Query"):
            self.sf.copy_hook_directives(['types', 'interfaces'], name, 'types')

        return ast

    def input_object_type_definition(self, ast):
        ''' Input handle
            * filter ou doublon
            * add filtered directive
                - @x_* directive work with *Patch input (we assumed that AddInput are managed by the BLA)
                - @w_* directieve work Add*Input input *Patch inputs, (used to alter a input field)
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


        if name.startswith('Add') and name.endswith('Input'):
            # This match the input field for the "Add" mutations
            type_name = re.match(r"Add(\w*)Input", name).groups()[0]
            if type_name:
                self.sf.copy_directives(type_name, ['types', 'interfaces'], name, 'inputs', r'^w_')
        elif name.endswith('Patch'):
            # This match the input field for the "Update" and "Remove" mutations
            type_name = re.match(r"(\w*)Patch", name).groups()[0]
            if type_name:
                self.sf.copy_directives(type_name, ['types', 'interfaces'], name, 'inputs', r'^w_')
                self.sf.copy_directives(type_name, ['types', 'interfaces'], name, 'inputs', r'^x_', set_default=True)

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


class DgraphSemantics(GraphqlSemantics):

    '''Dgraph semantic.
    '''
    _dgraph_directives = ["id", "search", "hasInverse", "remote", "custom", "auth", "lambda", "generate", "secret", "dgraph", "default", "cacheControl"]

    def interface_type_definition(self, ast):
        ''' Interface handle
            * filter or doublon
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.interfaces:
            self.sf.update_fields('interfaces', name, ast)
            return None
        else:
            self.sf.populate_data('interfaces', name, ast)

        return ast

    def object_type_definition(self, ast):
        '''Type handle
            * filter ot doublon
            * add implemented interfaces fields if not already presents
        '''
        assert(isinstance(ast, AST))
        ast = AST2(ast)

        name = self.sf.get_name(ast)
        # Watch out duplicate !
        if name in self.sf.types:
            self.sf.update_fields('types', name, ast)
            return None
        else:
            self.sf.populate_data('types', name, ast)
            self.sf.inherit_interface_dgraph(ast)

        return ast

    def directive(self, ast):
        ''' Filter out non-dgraph directive. '''
        if ast._name.name in self._dgraph_directives:
            return ast
        else:
            return ""


class SDL:
    '''Parse graphql file with semantics.

        The module interpret the rule name given by tatsu
        (with the synxax `rule_name:rule`) with the following semantics:
            * if rule_name starts with "_", it will be appended to
                the output with no special treatment.
            * rule_name can be defined as `name__code` where code
              can be [bb, bs, bs] that stands respectively for:
                * blank before
                * blank after
                * blank surrounded
            * `name` has a special treatment to manage space syntax.
            * `comment` are filtered out.
            * `args` do not make new line.
            * other rule are appended with a new line,
              specially the `field` rule name.

        Furthermore special rule are defined be Semantic class `*Semantics`.
        Reports to the methods documentation for further informantion.
    '''

    def __init__(self, settings):
        self.s = settings

        if not self.s['FILE']:
            raise ValueError("You must provide a GraphQL FILE argument.")
        else:
            infile = self.s['FILE'][0]

        self._grammar = open("gram/graphql.ebnf").read()
        self._target = open(infile).read()
        self.rew = re.compile(r'^\w+$')

        if self.s['--dgraph']:
            self.semantics = DgraphSemantics()
        else:
            self.semantics = GqlgenSemantics()

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

        # filter empty things
        out = [x for x in out if x != ""]

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
                    if _type in ("comment", "doc"):
                        try:
                            comment = "".join(o.comment)
                        except:
                            # bug in non dgraph...@debug
                            continue

                        if o.comment and comment.startswith("# Dgraph.Authorization"):
                            # keep comments
                            out += "\n\n"
                            pass
                        else:
                            # ignore comments
                            continue
                    elif _type == "args":
                        ignore_nl = True
                    elif _type in ("name"):
                        # Manage space between names

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
    parser = SDL(args)
    sdl = parser.stringify()

    if not args['--nv']:
        print(sdl)

    if args['--debug']:
        print(args)
        print()
        #asj = asjsons(ast)
        pprint(parser.ast, indent=2)
