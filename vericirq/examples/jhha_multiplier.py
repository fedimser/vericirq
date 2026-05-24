from typing import Iterator, Sequence

import cirq
import z3
from cirq import CCNOT, SWAP, CSWAP

from ..vericirq import GateVerifier, PermutationGate


def _rotate_right(register: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
    """In-place rotation matching QuantumArithmetic.Utils.RotateRight."""
    k = len(register)
    k1 = k // 2
    for i in range(k1):
        yield SWAP(register[i], register[k - 1 - i])
    for i in range(k1 - 1 + (k % 2)):
        yield SWAP(register[i], register[k - 2 - i])


def _add_nop(p: Sequence[cirq.Qid], b: Sequence[cirq.Qid], am: cirq.Qid) -> Iterator[cirq.OP_TREE]:
    """Computes p += am*b[1:] with b[0] restored to zero."""
    n = len(b) - 1
    assert len(p) == n + 1

    for i in range(n):
        yield CCNOT(am, b[i + 1], p[i])
        yield CSWAP(p[i], b[i], b[i + 1])

    yield CCNOT(am, b[n], p[n])

    for i in range(n - 1, -1, -1):
        yield CSWAP(p[i], b[i], b[i + 1])
        yield CCNOT(am, b[i], p[i])


class JhhaMultiplier(PermutationGate):
    """Adds product of two n-bit integers into a 2n-bit register.

    Computes: (a, b, p) := (a, b, (p + a*b) mod 2^(2n)).

    For multiplier behavior p := a*b, prepare p in zero state.

    Reference:
      Ancilla-Input and Garbage-Output Optimized Design of a Reversible Quantum Integer Multiplier
      Jayashree HV, Himanshu Thapliyal, Hamid R. Arabnia, V K Agrawal, 2016.
      https://arxiv.org/abs/1608.01228

    AI-assisted attribution:
      This implementation was AI-assisted by GitHub Copilot (model: GPT-5.3-Codex)
      by translating Q# implementation at:
      https://github.com/fedimser/quant-arith-re/blob/main/lib/src/QuantumArithmetic/JHHA2016.qs
    """

    def __init__(self, n: int):
        self.n = n

    @property
    def input_sizes(self):
        # Input registers: a (n), b (n), product/output (2n).
        return [self.n, self.n, 2 * self.n]

    @property
    def ancilla_size(self):
        # Temporary carry-in qubit (zcin) used by AddNop.
        return 1

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        assert len(qubits) == 4 * n + 1

        a = qubits[0:n]
        b = qubits[n : 2 * n]
        p = qubits[2 * n : 4 * n]
        zcin = qubits[4 * n]

        b_with_cin = [zcin] + list(b)
        p_hi = p[n - 1 : 2 * n]

        for i in range(0, n - 1):
            yield from _add_nop(p_hi, b_with_cin, a[i])
            yield from _rotate_right(p)

        yield from _add_nop(p_hi, b_with_cin, a[n - 1])


def verify_jhha_multiplier(mult: JhhaMultiplier):
    """Full formal specification for JHHA multiplier."""
    ver = GateVerifier(mult)
    a_in, b_in, p_in = ver.input_vars
    a_out, b_out, p_out = ver.output_vars

    # Precondition for pure multiplication mode.
    ver.add_precondition(p_in == 0)

    # Inputs are unchanged.
    ver.verify_spec(a_out == a_in).assert_ok()
    ver.verify_spec(b_out == b_in).assert_ok()

    # Product register contains a*b.
    a_in_ext = z3.ZeroExt(mult.n, a_in)
    b_in_ext = z3.ZeroExt(mult.n, b_in)
    ver.verify_spec(p_out == a_in_ext * b_in_ext).assert_ok()

    # Ancilla is released.
    ver.verify_ancillas().assert_ok()
