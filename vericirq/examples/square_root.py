from functools import cached_property
from typing import Iterator, Sequence

import cirq
import z3
from cirq import CNOT, SWAP, Qid, X

from ..vericirq import GateVerifier, PermutationGate
from .gidney_adder import GidneyAdder
from .subtract import AddSubGate


class SquareRoot(PermutationGate):
    """Non-restoring integer square root.

    Computes: (R, Ans) := (R - floor(sqrt(R))^2, floor(sqrt(R))).

    Registers are little-endian unsigned integers.

    Preconditions:
    - len(R) = n >= 1.
    - ceil(n / 2) <= len(Ans) <= n.
    - Ans is initialized to zero.

    Reference:
      T-count and Qubit Optimized Quantum Circuit Design of the
      Non-Restoring Square Root Algorithm, Muñoz-Coreas and Thapliyal (2018),
      https://arxiv.org/abs/1712.08254

    AI-assisted attribution:
      This implementation was AI-assisted by GitHub Copilot (model: GPT-5.3-Codex)
      by translating Q# implementation at:
      https://github.com/fedimser/quant-arith-re/blob/main/lib/src/QuantumArithmetic/MCT2018.qs
    """

    def __init__(self, n: int, ans_size: int):
        self.n = n
        self.ans_size = ans_size
        assert self.n >= 1
        assert self.ans_size >= (self.n + 1) // 2
        assert self.ans_size <= self.n

    @property
    def input_sizes(self) -> list[int]:
        return [self.n, self.ans_size]

    @cached_property
    def _internal_n(self) -> int:
        if self.n == 1:
            return 1
        return self.n + (2 - (self.n % 2))

    @cached_property
    def _pad_r_size(self) -> int:
        if self.n == 1:
            return 0
        return 2 - (self.n % 2)

    @cached_property
    def _pad_ans_size(self) -> int:
        if self.n == 1:
            return 0
        return max(self._internal_n - self.ans_size, 0)

    @cached_property
    def _work_size(self) -> int:
        if self.n == 1:
            return 0
        add_sub = AddSubGate(self._internal_n)
        ctrl_add = GidneyAdder(self._internal_n, self._internal_n, is_controlled=True)
        return max(add_sub.ancilla_size, ctrl_add.ancilla_size)

    @cached_property
    def ancilla_size(self) -> int:
        if self.n == 1:
            return 0
        # pad_R + optional pad_Ans + z + workspace shared by AddSub/CtrlAdd.
        return self._pad_r_size + self._pad_ans_size + 1 + self._work_size

    def _add_sub(
        self, ctrl: Qid, xs: list[Qid], ys: list[Qid], work: list[Qid]
    ) -> Iterator[cirq.OP_TREE]:
        assert len(xs) == len(ys)
        gate = AddSubGate(len(xs))
        yield gate.on(*([ctrl] + xs + ys + work[: gate.ancilla_size]))

    def _ctrl_add(
        self, ctrl: Qid, xs: list[Qid], ys: list[Qid], work: list[Qid]
    ) -> Iterator[cirq.OP_TREE]:
        assert len(xs) == len(ys)
        gate = GidneyAdder(len(xs), len(ys), is_controlled=True)
        yield gate.on(*([ctrl] + xs + ys + work[: gate.ancilla_size]))

    def _square_root_internal(
        self, r: list[Qid], ans: list[Qid], z: Qid, work: list[Qid]
    ) -> Iterator[cirq.OP_TREE]:
        n = len(r)
        assert n % 2 == 0
        assert n >= 4
        assert len(ans) == n

        m = n // 2
        f = ans[n - 2 : n] + ans[0 : n - 2]

        yield X(f[0])

        # Part 1: Initial subtraction.
        yield X(r[n - 2])
        yield CNOT(r[n - 2], r[n - 1])
        yield CNOT(r[n - 1], f[1])
        yield X(r[n - 1])
        yield CNOT(r[n - 1], z)
        yield CNOT(r[n - 1], f[2])
        yield X(r[n - 1])
        yield from self._add_sub(z, f[0:4], r[n - 4 : n], work)

        # Part 2: Conditional addition/subtraction.
        for i in range(2, m):
            yield X(z)
            yield CNOT(z, f[1])
            yield X(z)
            yield CNOT(f[2], z)
            yield CNOT(r[n - 1], f[1])
            yield X(r[n - 1])
            yield CNOT(r[n - 1], z)
            yield CNOT(r[n - 1], f[i + 1])
            yield X(r[n - 1])
            for j in range(i + 1, 2, -1):
                yield SWAP(f[j], f[j - 1])
            yield from self._add_sub(z, f[0 : 2 * i + 2], r[n - 2 * i - 2 : n], work)

        # Part 3: Remainder restoration.
        yield X(z)
        yield CNOT(z, f[1])
        yield X(z)
        yield CNOT(f[2], z)
        yield X(r[n - 1])
        yield CNOT(r[n - 1], z)
        yield CNOT(r[n - 1], f[m + 1])
        yield X(r[n - 1])
        yield X(z)
        yield from self._ctrl_add(z, f, r, work)
        yield X(z)
        for j in range(m + 1, 2, -1):
            yield SWAP(f[j], f[j - 1])
        yield CNOT(f[2], z)

        yield X(f[0])

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        qubits = list(qubits_seq)
        assert len(qubits) == self.n + self.ans_size + self.ancilla_size

        r = qubits[0 : self.n]
        ans = qubits[self.n : self.n + self.ans_size]

        if self.n == 1:
            yield SWAP(r[0], ans[0])
            return

        anc = qubits[self.n + self.ans_size :]
        pad_r = anc[0 : self._pad_r_size]
        offset = self._pad_r_size
        pad_ans = anc[offset : offset + self._pad_ans_size]
        offset += self._pad_ans_size
        z = anc[offset]
        work = anc[offset + 1 :]

        r_int = r + pad_r
        if self.ans_size > self._internal_n:
            ans_int = ans[0 : self._internal_n]
        else:
            ans_int = ans + pad_ans

        assert len(r_int) == self._internal_n
        assert len(ans_int) == self._internal_n

        yield from self._square_root_internal(r_int, ans_int, z, work)


def _is_square_root(a: z3.BitVecRef, b: z3.BitVecRef) -> z3.BoolRef:
    """Encodes condition "a = floor(sqrt(b))" for unsigned integers."""
    safe_width = max(2 * a.size() + 1, b.size())
    a_ext = z3.ZeroExt(safe_width - a.size(), a)
    b_ext = z3.ZeroExt(safe_width - b.size(), b)
    # Equivalent condition: a^2 <= b < (a+1)^2.
    return z3.And(z3.ULE(a_ext * a_ext, b_ext), z3.ULT(b_ext, (a_ext + 1) * (a_ext + 1)))


def verify_square_root(gate: SquareRoot):
    """Full formal specification for SquareRoot."""
    ver = GateVerifier(gate)
    r_in, ans_in = ver.input_vars
    r_out, ans_out = ver.output_vars

    ver.add_precondition(ans_in == 0)

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()

    # Verify that ans_out = floor(sqrt(r_in)).
    ver.verify_spec(_is_square_root(ans_out, r_in)).assert_ok()

    # Verify that r_out = r_in - ans_out^2.
    ans_ext = z3.ZeroExt(gate.n - gate.ans_size, ans_out)
    ver.verify_spec(r_out == r_in - ans_ext * ans_ext).assert_ok()
