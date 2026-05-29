from functools import cached_property
from typing import Iterator, Sequence

import cirq
from cirq import Qid
import z3
from cirq import X, CNOT

from vericirq.examples.gidney_adder import GidneyAdder

from ..vericirq import GateVerifier, PermutationGate


def apply_x_from_int(value: int, target: Sequence[Qid]) -> Iterator[cirq.Operation]:
    for i in range(len(target)):
        if (value >> i) % 2 == 1:
            yield X(target[i])


def apply_cx_from_int(value: int, ctrl: Qid, target: Sequence[Qid]) -> Iterator[cirq.Operation]:
    for i in range(len(target)):
        if (value >> i) % 2 == 1:
            yield CNOT(ctrl, target[i])


class ConstAdder(PermutationGate):
    """Adds constant to a register.

    Writes constant to ancilla and calls quantum-quantum adder.
    """

    def __init__(self, n: int, constant: int, is_controlled: bool = False):
        assert 0 <= constant < 2**n
        self.n = n
        self.constant = constant
        self.is_controlled = is_controlled

        self.adder = GidneyAdder(n, n)

    @property
    def input_sizes(self) -> list[int]:
        if self.is_controlled:
            return [self.n, 1]
        else:
            return [self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return self.n + self.adder.ancilla_size

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        qubits = list(qubits_seq)
        n = self.n
        if self.is_controlled:
            x, ctrl, y, anc = qubits[0:n], qubits[n], qubits[n + 1 : 2 * n + 1], qubits[2 * n + 1 :]
            yield from apply_cx_from_int(self.constant, ctrl, y)
            yield self.adder.on(*(y + x + anc))
            yield from apply_cx_from_int(self.constant, ctrl, y)
        else:
            x, y, anc = qubits[0:n], qubits[n : 2 * n], qubits[2 * n :]
            yield from apply_x_from_int(self.constant, y)
            yield self.adder.on(*(y + x + anc))
            yield from apply_x_from_int(self.constant, y)


def verify_const_adder(adder: ConstAdder):
    """Full formal specification for ConstAdder."""
    ver = GateVerifier(adder)
    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    if adder.is_controlled:
        x_in, ctrl_in = ver.input_vars
        x_out, ctrl_out = ver.output_vars
        ver.verify_spec(ctrl_out == ctrl_in).assert_ok()
        ver.verify_spec(x_out == z3.If(ctrl_in == 1, x_in + adder.constant, x_in)).assert_ok()
    else:
        x_in = ver.input_vars[0]
        x_out = ver.output_vars[0]
        ver.verify_spec(x_out == x_in + adder.constant).assert_ok()
