.ONESHELL:
.PHONY: gram gen

default: gen

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > graphql.ebnf
	# nmanual modification here to get this work with ast.py
	
parser:
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py type.graphql document

gen:
	cp -v directives.graphql gen/
	cp -v query.graphql gen/
	./ast.py type.graphql > gen/type.graphql

dgraph:
	cd ../database
	make all
	cd -


