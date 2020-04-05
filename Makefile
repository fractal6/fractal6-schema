.ONESHELL:
SHELL := /bin/bash
dgraphDirectives := $(shell echo "id search hasInverse" | tr " " "|")

.PHONY: type.graphql
default: gqlgen gqlgen2 type.graphql

#
# Generate Schemas
#

gqlgen:
	# Generate Gqlgen compatible GraphQL files with custom Query and Mutation.
	cp -v dgraph.graphql gen/
	cp -v directives.graphql gen/
	cp -v query.graphql gen/
	./ast.py type.graphql > gen/type.graphql

gqlgen2:
	# Generate Gqlgen compatible GraphQL files with dgraph generated Query and Mutation.
	./ast.py <(cat directives.graphql type.graphql ../database/schema.graphql) > gen2/schema.graphql

dgraph: type.graphql
	# Populate dgraph
	cd ../database
	make
	cd -

type.graphql:
	# Filter graphql files
	# * remove comments
	# * remove unknown directives
	@echo "Filtering $@"
	@sed -E "s/#.*$$//g; s/^directive .*$$//g; s/@($(dgraphDirectives))/§\1/Ig; s/@[[:alnum:]_]+\([^\)]+\)//g;  s/@[[:alnum:]_]+//g; s/§(id|search|hasinverse)/@\1/Ig;" $@ > gen_dgraph/$(basename $@).graphql
	#@sed -E "s/#.*$$//g;  s/^directive .*$$//g;  /@($(dgraphDirectives))/I!s/@.*//g" $@ > $(basename $@).d.graphql

#
# Build Parser
#
	
_parser:
	python3 -m tatsu gram/graphql.ebnf -o gram/graphql.py
	# help: gram/graphql.py --help
	# list rule: gram/graphql.py -l
	# parse file rule: gram/graphql.py type.graphql document
	#

_gram:
	mkdir -p gram/
	wget https://raw.githubusercontent.com/antlr/grammars-v4/master/graphql/GraphQL.g4 -O gram/graphql.g
	python3 -m tatsu.g2e graphql.g > graphql.ebnf
	# /!\ Warning:
	#	 Manual modification here to get this work with ast.py
