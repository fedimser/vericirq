from typing import Iterator, Sequence

import cirq
import z3
from cirq import CCNOT, CNOT

from ..vericirq import GateVerifier, PermutationGate


def maj(a, b, c):
    yield CNOT(c, a)
    yield CNOT(c, b)
    yield CCNOT(a, b, c)


def uma(a, b, c):
    yield (CCNOT(a, b, c),)
    yield CNOT(c, a)
    yield CNOT(a, b)


class CuccaroAdder(PermutationGate):
    """Adds 2 n-bit unsigned integers, with carry.

    Computes: (a, b, z) := (a, (a+b)%(2^n), z⊕(a+b)/(2^n)).

    Reference:
      A new quantum ripple-carry addition circuit
      Cuccaro, Draper, Kutin, Moulton, 2004.
      https://arxiv.org/pdf/quant-ph/0410184
    """

    def __init__(self, n: int):
        self.n = n

    @property
    def input_sizes(self):
        # First addend, second addend, carry.
        return [self.n, self.n, 1]

    @property
    def ancilla_size(self):
        return 1

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        assert len(qubits) == 2 * n + 2
        a, b, z, c = qubits[0:n], qubits[n : 2 * n], qubits[2 * n], qubits[2 * n + 1]

        yield from maj(c, b[0], a[0])
        for i in range(1, n):
            yield from maj(a[i - 1], b[i], a[i])
        yield CNOT(a[n - 1], z)
        for i in range(n - 1, 0, -1):
            yield from uma(a[i - 1], b[i], a[i])
        yield uma(c, b[0], a[0])


def verify_cuccaro_adder(adder: CuccaroAdder):
    """Full formal specification for Cuccaro adder."""
    ver = GateVerifier(adder)
    a_in, b_in, z_in = ver.input_vars
    a_out, b_out, z_out = ver.output_vars

    # First input is unchanged.
    ver.verify_spec(a_out == a_in).assert_ok()

    # Second input contains the sum modulo 2^n.
    ver.verify_spec(b_out == (a_in + b_in)).assert_ok()

    # Carry bit is flipped iff overflow happened.
    overflow = z3.Not(z3.BVAddNoOverflow(a_in, b_in, False))
    ver.verify_spec((z_in != z_out) == overflow).assert_ok()

    # Ancillas returned in zero state
    ver.verify_ancillas().assert_ok()
