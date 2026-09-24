# Conformance corpus

The normative test data for the language: each case is source text plus the
result every implementation must agree on. An implementation is conformant when
it reproduces these, which is what lets the private evaluator and any outside
implementation claim to speak the same language.

Kept as data rather than as Python tests on purpose — an implementation in
another language has to be able to consume it.

Layout (pending the first cases):

    conformance/
      parse/     source → expected AST
      reject/    source → the error it must be rejected with
