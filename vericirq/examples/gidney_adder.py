from typing import Iterator, Sequence

import cirq
import z3
from cirq import CCNOT, CNOT
from vericirq.gates import AND, IAND

from ..vericirq import GateVerifier, PermutationGate


def _half_adder_for_inc(x: cirq.Qid, y: cirq.Qid, carry_out: cirq.Qid) -> Iterator[cirq.OP_TREE]:
    yield CCNOT(x, y, carry_out)
    yield CNOT(x, y)


def _carry_for_inc(carry_in: cirq.Qid, x: cirq.Qid, y: cirq.Qid, carry_out: cirq.Qid) -> Iterator[cirq.OP_TREE]:
    yield CNOT(carry_in, x)
    yield CNOT(carry_in, y)
    yield AND(x, y, carry_out)
    yield CNOT(carry_in, carry_out)


def _uncarry_for_inc(carry_in: cirq.Qid, x: cirq.Qid, y: cirq.Qid, carry_out: cirq.Qid) -> Iterator[cirq.OP_TREE]:
    yield CNOT(carry_in, carry_out)
    yield IAND(x, y, carry_out)
    yield CNOT(carry_in, x)
    yield CNOT(x, y)


def _full_adder_for_inc(carry_in: cirq.Qid, x: cirq.Qid, y: cirq.Qid, carry_out: cirq.Qid) -> Iterator[cirq.OP_TREE]:
    yield CNOT(carry_in, x)
    yield CNOT(carry_in, y)
    yield CCNOT(x, y, carry_out)
    yield CNOT(carry_in, carry_out)
    yield CNOT(carry_in, x)
    yield CNOT(x, y)


class GidneyAdder(PermutationGate):
    """In-place Gidney ripple-carry adder.

    Computes: (x, y) := (x, y + x) modulo 2^len(y), with little-endian registers.

    Preconditions:
    - len(x) = n >= 1
    - len(y) = m >= n

    Reference:
      "Halving the cost of quantum addition", Craig Gidney, https://arxiv.org/pdf/1709.06648.

    AI-assisted attribution:
      This implementation was AI-assisted by GitHub Copilot (model: GPT-5.3-Codex)
      by translating Q# implementation at:
      https://github.com/microsoft/qsharp/blob/main/library/std/src/Std/Arithmetic.qs
    """

    def __init__(self, n: int, m: int | None = None):
        self.n = n
        self.m = n if m is None else m
        assert self.n > 0
        assert self.m >= self.n

    @property
    def input_sizes(self) -> list[int]:
        # x, y registers.
        return [self.n, self.m]

    @property
    def ancilla_size(self) -> int:
        x_eff_len = self.m - 1 if self.m - self.n >= 2 else self.n
        padding_len = max(self.m - self.n - 1, 0)
        carries_len = x_eff_len if x_eff_len > 1 else 0
        return padding_len + carries_len

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n, m = self.n, self.m
        assert len(qubits) == n + m + self.ancilla_size
        x = list(qubits[0:n])
        y = list(qubits[n : n + m])
        anc = list(qubits[n + m :])

        padding_len = max(m - n - 1, 0)
        x_eff_len = m - 1 if m - n >= 2 else n
        assert x_eff_len >= 1

        padding = anc[:padding_len]
        carries = anc[padding_len : padding_len + (x_eff_len if x_eff_len > 1 else 0)]

        x_eff = x + padding
        assert len(x_eff) == x_eff_len

        if x_eff_len == 1:
            if m == 1:
                yield CNOT(x_eff[0], y[0])
            else:
                yield from _half_adder_for_inc(x_eff[0], y[0], y[1])
            return

        yield AND(x_eff[0], y[0], carries[0])

        for i in range(1, x_eff_len - 1):
            yield from _carry_for_inc(carries[i - 1], x_eff[i], y[i], carries[i])

        if x_eff_len == m:
            yield CNOT(carries[x_eff_len - 2], x_eff[x_eff_len - 1])
            yield CNOT(x_eff[x_eff_len - 1], y[x_eff_len - 1])
            yield CNOT(carries[x_eff_len - 2], x_eff[x_eff_len - 1])
        else:
            yield from _full_adder_for_inc(carries[x_eff_len - 2], x_eff[x_eff_len - 1], y[x_eff_len - 1], y[x_eff_len])

        for i in range(x_eff_len - 2, 0, -1):
            yield from _uncarry_for_inc(carries[i - 1], x_eff[i], y[i], carries[i])

        yield IAND(x_eff[0], y[0], carries[0])
        yield CNOT(x_eff[0], y[0])


def verify_gidney_adder(adder: GidneyAdder):
    """Full formal specification for GidneyAdder."""
    ver = GateVerifier(adder)
    x_in, y_in = ver.input_vars
    x_out, y_out = ver.output_vars

    ver.verify_spec(x_out == x_in).assert_ok()

    x_ext = z3.ZeroExt(adder.m - adder.n, x_in)
    ver.verify_spec(y_out == (y_in + x_ext)).assert_ok()

    ver.verify_ancillas().assert_ok()

    ver.verify_and_gates().assert_ok()
