from typing import Iterator, Sequence

import cirq
import z3
from cirq import CNOT, SWAP, Qid, X

from ..vericirq import GateVerifier, PermutationGate
from .gidney_adder import GidneyAdder
from .subtract import AddSubGate, SubtractGate


class DivideRestoringGate(PermutationGate):
    """Computes a,b,c:=(a%b,b,a/b).

    Constraints:
      * a,b,c must have the same number of qubits n.
      * 0 <= a < 2^n.
      * 0 < b < 2^(n-1).
      * c must be initialized to zeros.

    Reference:
      Quantum Circuit Designs of Integer Division Optimizing T-count and T-depth,
      Thapliyal, Munoz-Coreas, Varun, Humble, 2019, https://arxiv.org/pdf/1809.09732.
    """

    def __init__(self, n):
        self.n = n
        self.ctrl_adder = GidneyAdder(n, n, is_controlled=True)
        self.subtractor = SubtractGate(n)
        self._ancilla_size = max(self.ctrl_adder.ancilla_size, self.subtractor.ancilla_size)

    @property
    def input_sizes(self):
        return [self.n, self.n, self.n]

    @property
    def ancilla_size(self):
        return self._ancilla_size

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        qubits = list(qubits_seq)
        q, b, r, anc = qubits[0:n], qubits[n : 2 * n], qubits[2 * n : 3 * n], qubits[3 * n :]
        anc_for_adder = anc[: self.ctrl_adder.ancilla_size]
        anc_for_sub = anc[: self.subtractor.ancilla_size]

        for i in range(1, n + 1):
            y = q[n - i : n] + r[0 : n - i]
            yield self.subtractor.on(*(b + y + anc_for_sub))
            yield CNOT(y[n - 1], r[n - i])
            yield self.ctrl_adder.on(*([r[n - i]] + b + y + anc_for_adder))
            yield X(r[n - i])


def verify_divide_restoring_gate(gate: DivideRestoringGate):
    """Full formal specification for DivideRestoringGate."""
    n = gate.n
    ver = GateVerifier(gate)
    a_in, b_in, c_in = ver.input_vars
    a_out, b_out, c_out = ver.output_vars

    ver.add_precondition(0 < b_in)
    ver.add_precondition(b_in < 2 ** (n - 1))
    ver.add_precondition(c_in == 0)

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    ver.verify_spec(a_out == z3.URem(a_in, b_in)).assert_ok()
    ver.verify_spec(b_out == b_in).assert_ok()
    ver.verify_spec(c_out == z3.UDiv(a_in, b_in)).assert_ok()


class DivideNonRestoringGate(PermutationGate):
    """Computes a,b,c:=(a%b,b,a/b).

    Constraints:
      * Register sizes must be (n, n-1, n).
      * b > 0.
      * c must be initialized to zeros.

    Reference:
      Quantum Circuit Designs of Integer Division Optimizing T-count and T-depth,
      Thapliyal, Munoz-Coreas, Varun, Humble, 2019, https://arxiv.org/pdf/1809.09732.
    """

    def __init__(self, n):
        self.n = n
        self.ctrl_adder = GidneyAdder(n - 1, n - 1, is_controlled=True)
        self.subtractor = SubtractGate(n)
        self.add_sub_gate = AddSubGate(n)

        self._ancilla_size = max(
            self.ctrl_adder.ancilla_size, self.subtractor.ancilla_size, self.add_sub_gate.ancilla_size
        )

    @property
    def input_sizes(self):
        return [self.n, self.n - 1, self.n]

    @property
    def ancilla_size(self):
        return self._ancilla_size

    def _subtract(self, x: list[Qid], y: list[Qid]) -> Iterator[cirq.OP_TREE]:
        yield self.subtractor.on(*(x + y + self.anc[: self.subtractor.ancilla_size]))

    def _add_sub(self, ctrl: Qid, x: list[Qid], y: list[Qid]) -> Iterator[cirq.OP_TREE]:
        yield self.add_sub_gate.on(*([ctrl] + x + y + self.anc[: self.add_sub_gate.ancilla_size]))

    def _ctrl_add(self, ctrl: Qid, x: list[Qid], y: list[Qid]) -> Iterator[cirq.OP_TREE]:
        yield self.ctrl_adder.on(*([ctrl] + x + y + self.anc[: self.ctrl_adder.ancilla_size]))

    def _divide_internal(self, a: list[Qid], b: list[Qid], c: list[Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        r = a[0 : n - 1]
        q = [a[n - 1]] + c

        yield from self._subtract(b, q)
        for i in range(1, n):
            yield X(q[n - i])
            y = r[n - 1 - i : n - 1] + q[0 : n - i]
            yield from self._add_sub(q[n - i], b, y)
        yield from self._ctrl_add(q[0], b[0 : n - 1], r)
        yield X(q[0])

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        qubits = list(qubits_seq)
        a, b, c = qubits[0:n], qubits[n : 2 * n - 1], qubits[2 * n - 1 : 3 * n - 1]
        self.anc = qubits[3 * n - 1 :]
        yield from self._divide_internal(a, b + [c[0]], c[1:])
        yield SWAP(a[n - 1], c[0])


def verify_divide_non_restoring_gate(gate: DivideNonRestoringGate):
    """Full formal specification for DivideRestoringGate."""
    ver = GateVerifier(gate)
    a_in, b_in, c_in = ver.input_vars
    a_out, b_out, c_out = ver.output_vars
    b_in_ext = z3.ZeroExt(1, b_in)

    ver.add_precondition(0 < b_in)
    ver.add_precondition(c_in == 0)

    ver.add_precondition(a_in == 15)
    ver.add_precondition(b_in == 3)

    ver.add_precondition(a_out == 0)
    ver.add_precondition(c_out == 5)

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    ver.verify_spec(a_out == z3.URem(a_in, b_in_ext)).assert_ok()
    ver.verify_spec(b_out == b_in).assert_ok()
    ver.verify_spec(c_out == z3.UDiv(a_in, b_in_ext)).assert_ok()
