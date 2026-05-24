from functools import cached_property
from typing import Iterator, Optional, Sequence

import cirq
import z3
from cirq import CCNOT, CNOT
from vericirq.gates import AND, IAND

from cirq import Qid

from ..vericirq import GateVerifier, PermutationGate


def _cnot(x: Qid, y: Qid, ctrl: Optional[Qid] = None):
    if ctrl is None:
        return CNOT(x, y)
    else:
        return CCNOT(ctrl, x, y)


def _half_adder_for_inc(
    x: Qid,
    y: Qid,
    carry_out: Qid,
    ctrl: Optional[Qid] = None,
    helper: Optional[Qid] = None,
) -> Iterator[cirq.OP_TREE]:
    if ctrl is None:
        yield CCNOT(x, y, carry_out)
        yield CNOT(x, y)
    else:
        assert helper is not None
        yield AND(x, y, helper)
        yield AND(ctrl, helper, carry_out)
        yield IAND(x, y, helper)
        yield CCNOT(ctrl, x, y)


def _carry_for_inc(
    carry_in: Qid,
    x: Qid,
    y: Qid,
    carry_out: Qid,
) -> Iterator[cirq.OP_TREE]:
    # Controlled version is identical to uncontrolled.
    yield CNOT(carry_in, x)
    yield CNOT(carry_in, y)
    yield AND(x, y, carry_out)
    yield CNOT(carry_in, carry_out)


def _uncarry_for_inc(
    carry_in: Qid,
    x: Qid,
    y: Qid,
    carry_out: Qid,
    ctrl: Optional[Qid] = None,
) -> Iterator[cirq.OP_TREE]:
    if ctrl is None:
        yield CNOT(carry_in, carry_out)
        yield IAND(x, y, carry_out)
        yield CNOT(carry_in, x)
        yield CNOT(x, y)
    else:
        yield CNOT(carry_in, carry_out)
        yield IAND(x, y, carry_out)
        yield CCNOT(ctrl, x, y)
        yield CNOT(carry_in, x)
        yield CNOT(carry_in, y)


def _full_adder_for_inc(
    carry_in: Qid,
    x: Qid,
    y: Qid,
    carry_out: Qid,
    ctrl: Optional[Qid] = None,
    helper: Optional[Qid] = None,
) -> Iterator[cirq.OP_TREE]:
    if ctrl is None:
        yield CNOT(carry_in, x)
        yield CNOT(carry_in, y)
        yield CCNOT(x, y, carry_out)
        yield CNOT(carry_in, carry_out)
        yield CNOT(carry_in, x)
        yield CNOT(x, y)
    else:
        assert helper is not None
        yield from _carry_for_inc(carry_in, x, y, helper)
        yield CCNOT(ctrl, helper, carry_out)
        yield from _uncarry_for_inc(carry_in, x, y, helper, ctrl=ctrl)


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

    def __init__(self, n: int, m: int, is_controlled: bool = False):
        self.n = n
        self.m = m
        self.is_controlled = is_controlled
        assert self.n > 0
        assert self.m >= self.n

    @property
    def input_sizes(self) -> list[int]:
        if self.is_controlled:
            return [1, self.n, self.m]
        else:
            return [self.n, self.m]

    @cached_property
    def ancilla_size(self) -> int:
        x_eff_len = self.m - 1 if self.m - self.n >= 2 else self.n
        padding_len = max(self.m - self.n - 1, 0)
        carries_len = x_eff_len if x_eff_len > 1 else 0
        ctrl_len = 1 if self.is_controlled else 0
        return padding_len + carries_len + ctrl_len

    def _decompose_(self, qubits_seq: Sequence[Qid]) -> Iterator[cirq.OP_TREE]:
        n, m = self.n, self.m
        qubits = list(qubits_seq)

        ctrl = None  # type: Optional[Qid]
        if self.is_controlled:
            assert len(qubits) == 1 + n + m + self.ancilla_size
            ctrl = qubits[0]
            qubits = qubits[1:]
        else:
            assert len(qubits) == n + m + self.ancilla_size

        x = qubits[0:n]
        y = qubits[n : n + m]
        anc = qubits[n + m :]

        padding_len = max(m - n - 1, 0)
        x_eff_len = m - 1 if m - n >= 2 else n
        assert x_eff_len >= 1

        helper = None  # type: Optional[Qid]
        if self.is_controlled:
            helper = anc[-1]
            anc = anc[:-1]

        padding = anc[:padding_len]
        carries = anc[padding_len : padding_len + (x_eff_len if x_eff_len > 1 else 0)]

        x_eff = x + padding
        assert len(x_eff) == x_eff_len

        if x_eff_len == 1:
            if m == 1:
                yield _cnot(x_eff[0], y[0], ctrl=ctrl)
            else:
                yield from _half_adder_for_inc(x_eff[0], y[0], y[1], ctrl=ctrl, helper=helper)
            return

        yield AND(x_eff[0], y[0], carries[0])

        for i in range(1, x_eff_len - 1):
            yield from _carry_for_inc(carries[i - 1], x_eff[i], y[i], carries[i])

        if x_eff_len == m:
            yield CNOT(carries[x_eff_len - 2], x_eff[x_eff_len - 1])
            yield _cnot(x_eff[x_eff_len - 1], y[x_eff_len - 1], ctrl=ctrl)
            yield CNOT(carries[x_eff_len - 2], x_eff[x_eff_len - 1])
        else:
            yield from _full_adder_for_inc(
                carries[x_eff_len - 2],
                x_eff[x_eff_len - 1],
                y[x_eff_len - 1],
                y[x_eff_len],
                ctrl=ctrl,
                helper=helper,
            )

        for i in range(x_eff_len - 2, 0, -1):
            yield from _uncarry_for_inc(carries[i - 1], x_eff[i], y[i], carries[i], ctrl=ctrl)

        yield IAND(x_eff[0], y[0], carries[0])
        yield _cnot(x_eff[0], y[0], ctrl=ctrl)


def verify_gidney_adder(adder: GidneyAdder):
    """Full formal specification for GidneyAdder."""
    ver = GateVerifier(adder)

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    if adder.is_controlled:
        ctrl_in, x_in, y_in = ver.input_vars
        ctrl_out, x_out, y_out = ver.output_vars

        ver.verify_spec(ctrl_in == ctrl_out).assert_ok()
        ver.verify_spec(x_out == x_in).assert_ok()

        x_ext = z3.ZeroExt(adder.m - adder.n, x_in)
        ver.verify_spec(y_out == z3.If(ctrl_in == 1, y_in + x_ext, y_in)).assert_ok()
    else:
        x_in, y_in = ver.input_vars
        x_out, y_out = ver.output_vars

        ver.verify_spec(x_out == x_in).assert_ok()

        x_ext = z3.ZeroExt(adder.m - adder.n, x_in)
        ver.verify_spec(y_out == (y_in + x_ext)).assert_ok()
