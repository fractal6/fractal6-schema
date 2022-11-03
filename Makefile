.ONESHELL:
SHELL := /bin/bash

.PHONY: dgraph_in

# 1. make dgraph
# 2. make schema
# --
default: schema
all: parser dgraph schema 
schema: gqlgen_in
schema_all: dgraph schema

# Populate Dgraph schema
dgraph: dgraph_in
	# Populate dgraph and fetch schema out
	cd ../fractal6-db && \
		make update && \
		make fetch_schema && \
		cd - && \
		cp ../fractal6-db/schema/schema_out.graphql gen_dgraph_out/schema.graphql

# Generate Dgraph input schema
dgraph_in:
	# Generate Dgraph input GraphQL.
	./gqlast.py --dgraph <(cat graphql/errors.graphql graphql/fractal6.graphql) > gen_dgraph_in/schema.graphql
	# Filter-in dgraph directives
	#sed -Ei "s/#.*$$//g; s/^directive .*$$//g; s/@(id|search|hasInverse)/§\1/Ig; s/@[[:alnum:]_]+\([^\)]+\)//g; s/@[[:alnum:]_]+//g; s/§(id|search|hasinverse)/@\1/Ig;" $@

# Build final schema by mergin everithing.
gqlgen_in:
	# Generate Gqlgen compatible GraphQL files with dgraph generated Query and Mutation.
	# Fish shell: use `(cat .. | psub)` instead.
	./gqlast.py <(cat graphql/directives.graphql graphql/fractal6.graphql gen_dgraph_out/schema.graphql) > gen/schema.graphql


#
# Build Parser
#
	
parser:
	# Build the parser from the grammar
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py schema.graphql document

_gram:
	# <!>Warning<!>
	# Get Orinal Grammar
	nop && \
		mkdir -p gram/ && \
		wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g && \
		python3 -m tatsu.g2e graphql.g > gram/graphql.ebnf
	# Manual modification here to get this work with gqlast.py
