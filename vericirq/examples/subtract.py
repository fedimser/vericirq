from functools import cached_property
from typing import Iterator, Sequence

import cirq
import z3
from cirq import CCNOT, CNOT, X

from vericirq.examples.gidney_adder import GidneyAdder

from ..vericirq import GateVerifier, PermutationGate


class SubtractGate(PermutationGate):
    """Computes b := (b-a)%(2^n)."""

    def __init__(self, n):
        self.n = n
        self.adder = GidneyAdder(n, n)

    @property
    def input_sizes(self) -> list[int]:
        return [self.n, self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return self.adder.ancilla_size

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        yield from X.on_each(qubits[self.n : 2 * self.n])
        yield self.adder.on(*qubits)
        yield from X.on_each(qubits[self.n : 2 * self.n])


def verify_subtract_gate(gate: SubtractGate):
    """Full formal specification for SubtractGate."""
    ver = GateVerifier(gate)
    a_in, b_in = ver.input_vars
    a_out, b_out = ver.output_vars

    ver.verify_spec(a_out == a_in).assert_ok()
    ver.verify_spec(b_out == (b_in - a_in)).assert_ok()
    ver.verify_ancillas().assert_ok()


class AddSubGate(PermutationGate):
    """Computes b-=a if ctrl=1, and b+=a if ctrl=0."""

    def __init__(self, n):
        self.n = n
        self.adder = GidneyAdder(n, n)

    @property
    def input_sizes(self) -> list[int]:
        return [1, self.n, self.n]

    @property
    def ancilla_size(self) -> int:
        return self.adder.ancilla_size

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        ctrl, b = qubits[0], qubits[self.n + 1 : 2 * self.n + 1]
        for i in range(self.n):
            yield CNOT(ctrl, b[i])
        yield self.adder.on(*qubits[1:])
        for i in range(self.n):
            yield CNOT(ctrl, b[i])


def verify_add_sub_gate(gate: AddSubGate):
    """Full formal specification for AddSubGate."""
    ver = GateVerifier(gate)
    ctrl_in, a_in, b_in = ver.input_vars
    ctrl_out, a_out, b_out = ver.output_vars

    ver.verify_spec(ctrl_out == ctrl_in).assert_ok()
    ver.verify_spec(a_out == a_in).assert_ok()
    ver.verify_spec(b_out == z3.If(ctrl_in == 1, b_in - a_in, b_in + a_in)).assert_ok()
    ver.verify_ancillas().assert_ok()
