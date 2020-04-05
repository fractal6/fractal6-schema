
As dgraph doesnt suppoet custom directives at the time of this project is written, this repo contains parser that generate valid graphql schema for 

* dgraph: remove custom directives and comments (see issue #?).
* gqlgen and graphql-elm: dgraph shema is used to provide gqlgen and graphql-elm, whith custom logics:
        * types that implement interfaces need the inherit the fields of the mother interface (not needed for dgraph).
        * remove interface reference and change to standard type to simplify gqlgen implementation.
        * input directives are moved to the generated input od dgraph
        * dgraph types arguments are copied to original type if they don't exist.
        * manage duplicated type.

The generator output files in the fowlowing directories:

* gen/: Shema used by fractal6.go (glqgen) with custom queries and mutations.

* gen2/ Shema used by fractal6.go (glqgen) with custom schema from dgraph introspection.
