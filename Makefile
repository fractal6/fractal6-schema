.ONESHELL:
SHELL := /bin/bash
dgraphDirectives := $(shell echo "id search hasInverse" | tr " " "|")

.PHONY: gen_dgraph_in/types.graphql
default: schema
schema: gqlgen2 gen_dgraph_in/types.graphql
all: dgraph schema # Contains gen_dgraph_in/types.graphql

#
# Generate Schemas
#

gqlgen:
	# THIS IS FOR TESTING
	# Generate Gqlgen compatible GraphQL files with custom Query and Mutation.
	cp -v graphql/dgraph.graphql gen/
	cp -v graphql/directives.graphql gen/
	cp -v graphql/query.graphql gen/
	./gqlast.py graphql/types.graphql > gen/types.graphql

gqlgen2:
	# Generate Gqlgen compatible GraphQL files with dgraph generated Query and Mutation.
	./gqlast.py <(cat graphql/directives.graphql graphql/types.graphql gen_dgraph_out/schema.graphql) > gen2/schema.graphql

dgraph: gen_dgraph_in/types.graphql
	# Populate dgraph
	cd ../database
	make update
	make fetch_schema 
	cd -
	cp ../database/schema.graphql gen_dgraph_out/schema.graphql

gen_dgraph_in/types.graphql:
	# Generate Dgraph input GraphQL.
	./gqlast.py --dgraph graphql/types.graphql > $@
	@sed -Ei "s/#.*$$//g; s/^directive .*$$//g; s/@($(dgraphDirectives))/§\1/Ig; s/@[[:alnum:]_]+\([^\)]+\)//g; s/@[[:alnum:]_]+//g; s/§(id|search|hasinverse)/@\1/Ig;" $@


#
# Build Parser
#
	
_parser:
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py types.graphql document

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > gram/graphql.ebnf
	# /!\ Warning:
	#	 Manual modification here to get this work with gqlast.py
