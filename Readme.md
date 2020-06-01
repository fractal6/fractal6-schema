
This repo contains the core schema of the project and the binary `gqlast.py` that parses and generates GraphQL files from source schema to feed the libraries in use such as `gqlgen`, `dgraph` and `elm-graphql`.


### Input schema

The source schema are defined in the following files:
* [graphql/types.graphql](graphql/types.graphql): Defines the main data structures of Fractal6, such as the graph structures of organisations the tensions etc.
* [graphql/directives.graphql](graphql/types.graphql): defines the custom directives implemented in the Business Logic Layer.

### GraphQL applications

The `graphql/` directory contains the schema source of the all other schema and are used to generated valid GraphQL scheme for the following applications:

* **dgraph** (almost native GraphQL support):
    * remove custom directives and comments.
    * types that implements interface doesn't cant redefined the fiel -> Only the interface field are kept because there are supposed to be more flexible.
* **gqlgen** and **elm-graphql** (GraphQL support): dgraph schema is used to provide gqlgen and elm-graphql with custom rational:
    * types that implement interfaces need the inherit the fields of the mother interface (not needed for dgraph).
    * change `interface` type to `type` type to simplify gqlgen implementation.
    * input directives (`@alter_*` and `@patch_*` directives) are moved to the input type generated by dgraph
    * dgraph types arguments are copied to original type if they don't exist.
    * manage duplicated type.


### Output directories
The generator output files in the following directories:

* `gen/`: Schema used by fractal6.go (glqgen) with custom queries and mutations.
* `gen2/`: Schema used by fractal6.go (glqgen) and fractal6.elm (graphql-elm) with custom schema from dgraph introspection.
* `gen_dgraph_in`: the schema use to alter dgraph database.
* `gen_dgraph_out`: the schema generated by dgraph, with automatic queries, mutations and inputs generated.
