.ONESHELL:
SHELL := /bin/bash
dgraphDirectives := $(shell echo "id search hasInverse" | tr " " "|")

.PHONY: gen_dgraph_in/types.graphql
default: schema
schema: gqlgen_in
schema_all: dgraph schema # Contains gen_dgraph_in/types.graphql

#
# Generate Schemas
#

gqlgen_in:
	# Generate Gqlgen compatible GraphQL files with dgraph generated Query and Mutation.
	./gqlast.py <(cat graphql/directives.graphql graphql/types.graphql gen_dgraph_out/schema.graphql) > gen/schema.graphql

dgraph: gen_dgraph_in/types.graphql
	# Populate dgraph and fetch schema out
	cd ../database
	make update
	make fetch_schema 
	cd -
	cp ../database/graph/schema_out.graphql gen_dgraph_out/schema.graphql

gen_dgraph_in/types.graphql:
	# Generate Dgraph input GraphQL.
	./gqlast.py --dgraph graphql/types.graphql > $@
	@sed -Ei "s/#.*$$//g; s/^directive .*$$//g; s/@($(dgraphDirectives))/§\1/Ig; s/@[[:alnum:]_]+\([^\)]+\)//g; s/@[[:alnum:]_]+//g; s/§(id|search|hasinverse)/@\1/Ig;" $@


#
# Build Parser
#
	
_parser:
	# Build the parser from the grammar
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py types.graphql document

_gram:
	# Get Orinal Grammar
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > gram/graphql.ebnf
	# /!\ Warning:
	#	 Manual modification here to get this work with gqlast.py
