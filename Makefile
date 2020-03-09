.PHONY: gram gen

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > graphql.ebnf
	# nmanual modification here to get this work with ast.py

gen:
	cp directives.graphql gen/
	cp type.graphql gen/
	cp query.graphql gen/
