.ONESHELL:
.PHONY: _gram gqlgen

default: gqlgen

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > graphql.ebnf
	# nmanual modification here to get this work with ast.py
	
_parser:
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py type.graphql document

gqlgen:
	# Generate Gqlgen compatible GraphQL files.
	cp -v dgraph.graphql gen/
	cp -v directives.graphql gen/
	cp -v query.graphql gen/
	./ast.py type.graphql > gen/type.graphql

dgraph:
	# populate dgraph
	cd ../database
	make
	cd -


