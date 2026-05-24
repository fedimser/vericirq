This folder contains some artihemtic circuits we use to test the library. 

The purpose of these examples is to demonstrate how to use the library: how to define gate and how to write specs.
Also these examples are used for unit tests. 

It is not intended to be a comprehensive library of quantum artihmetic algorithms.

Each example contains:
 1. Cirquit definition as PermutationGate.
 2. Formal specification for the gate. It is a function that takes a gate, uses VeriCirq to check several conditions and asserts that all checks return OK.
