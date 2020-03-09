.PHONY: gram gen

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > graphql.ebnf
	# nmanual modification here to get this work with ast.py

gen:
	cp -v directives.graphql gen/
	cp -v query.graphql gen/
	./ast.py type.graphql > gen/type.graphql
