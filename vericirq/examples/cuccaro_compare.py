from typing import Iterator, Optional, Sequence

import cirq
import z3
from cirq import X, CCNOT, CNOT, Qid

from ..vericirq import GateVerifier, PermutationGate
from .cuccaro_adder import maj, uma


def maj_inv(a: Qid, b: Qid, c: Qid):
    yield CCNOT(a, b, c)
    yield CNOT(c, b)
    yield CNOT(c, a)


class CuccaroCompare(PermutationGate):
    """Compares 2 n-bit unsigned integers.

    Computes: (a, b, ans) := (a, b, ans⊕(a>b)).

    Reference: https://arxiv.org/pdf/2112.11358 (fig.7).
    """

    def __init__(self, n: int, is_controlled: bool = False):
        self.n = n
        self.is_controlled = is_controlled

    @property
    def input_sizes(self):
        if self.is_controlled:
            # x, y, ans, control.
            return [self.n, self.n, 1, 1]
        else:
            # x, y, ans.
            return [self.n, self.n, 1]

    @property
    def ancilla_size(self):
        return 1

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        a, b, ans = qubits[0:n], qubits[n : 2 * n], qubits[2 * n]
        ctrl = None  # type: Optional[Qid]
        if self.is_controlled:
            assert len(qubits) == 2 * n + 3
            ctrl = qubits[2 * n + 1]
            anc = qubits[2 * n + 2]
        else:
            assert len(qubits) == 2 * n + 2
            anc = qubits[2 * n + 1]

        yield from [X(q) for q in b]

        yield from maj(anc, a[0], b[0])

        for i in range(1, n):
            yield from maj(b[i - 1], a[i], b[i])

        if self.is_controlled:
            yield CCNOT(ctrl, b[n - 1], ans)
        else:
            yield CNOT(b[n - 1], ans)

        for i in reversed(range(1, n)):
            yield from maj_inv(b[i - 1], a[i], b[i])

        yield from maj_inv(anc, a[0], b[0])

        yield from [X(q) for q in b]


def verify_cuccaro_compare(gate: CuccaroCompare):
    """Full formal specification for CuccaroCompare."""
    ver = GateVerifier(gate)
    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    a_in, b_in, ans_in = ver.input_vars[0:3]
    a_out, b_out, ans_out = ver.output_vars[0:3]
    ans_flipped = ans_in != ans_out

    # Inputs are unchanged.
    ver.verify_spec(a_out == a_in).assert_ok()
    ver.verify_spec(b_out == b_in).assert_ok()

    if gate.is_controlled:
        ctrl_in = ver.input_vars[3]
        ctrl_out = ver.output_vars[3]
        ver.verify_spec(ctrl_in == ctrl_out).assert_ok()
        ver.verify_spec(
            ans_flipped == z3.And(ctrl_in == 1, z3.UGT(a_in, b_in))
        ).assert_ok()
    else:
        ver.verify_spec(ans_flipped == z3.UGT(a_in, b_in)).assert_ok()
