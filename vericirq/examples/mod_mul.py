from functools import cached_property
from typing import Iterator, Sequence

import cirq
import z3
from cirq import CNOT, Qid, X

from ..vericirq import GateVerifier, PermutationGate
from .const_adder import ConstAdder
from .gidney_adder import GidneyAdder
from .cuccaro_compare import CuccaroCompare


class ModAdder(PermutationGate):
    """Addition of 2 numbers modulo constant.

    Computes (x, y) := x, ((x+y)%p).

    Reference: https://arxiv.org/pdf/1706.06752 (fig.3).

    Uses Gidney adder for addition/subtraction and Cuccaro comparator for comparison.
    """

    def __init__(self, n: int, p: int, is_controlled: bool = False):
        assert 0 <= p < 2**n
        self.n = n
        self.p = p
        self.is_controlled = is_controlled

        # Prepare gates.
        self.adder1 = GidneyAdder(n, n + 1, is_controlled=is_controlled)
        self.adder2 = ConstAdder(n + 1, 2 ** (n + 1) - self.p)
        self.adder3 = ConstAdder(n, self.p, is_controlled=True)
        self.cmp4 = CuccaroCompare(n, is_controlled=is_controlled)

    @property
    def input_sizes(self) -> list[int]:
        if self.is_controlled:
            return [self.n, self.n, 1]
        else:
            return [self.n, self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return 1 + max(
            self.adder1.ancilla_size,
            self.adder2.ancilla_size,
            self.adder3.ancilla_size,
            self.cmp4.ancilla_size,
        )

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        qubits = list(qubits_seq)
        n = self.n
        x = qubits[0:n]
        y = qubits[n : 2 * n]
        ctrl = None
        if self.is_controlled:
            ctrl = qubits[2 * n]
            anc = qubits[2 * n + 1 :]
        else:
            anc = qubits[2 * n :]
        carry, anc = anc[0], anc[1:]

        # Step 1. Add.
        if ctrl is not None:
            yield self.adder1.on(*([ctrl] + x + y + [carry] + anc[: self.adder1.ancilla_size]))
        else:
            yield self.adder1.on(*(x + y + [carry] + anc[: self.adder1.ancilla_size]))

        # Step 2. "-p".
        yield self.adder2.on(*(y + [carry] + anc[: self.adder2.ancilla_size]))

        # Step 3. Controlled "+p".
        yield self.adder3.on(*(y + [carry] + anc[: self.adder3.ancilla_size]))

        # Step 4. Uncompute carry (with comparator).
        if ctrl is not None:
            yield self.cmp4.on(*(x + y + [carry, ctrl] + anc[: self.cmp4.ancilla_size]))
        else:
            yield self.cmp4.on(*(x + y + [carry] + anc[: self.cmp4.ancilla_size]))
        yield X(carry)


def verify_mod_adder(gate: ModAdder):
    ver = GateVerifier(gate)

    x_in = z3.ZeroExt(1, ver.input_vars[0])
    y_in = z3.ZeroExt(1, ver.input_vars[1])
    x_out = z3.ZeroExt(1, ver.output_vars[0])
    y_out = z3.ZeroExt(1, ver.output_vars[1])

    ver.add_precondition(z3.ULT(x_in, gate.p))
    ver.add_precondition(z3.ULT(y_in, gate.p))

    ver.verify_spec(x_out == x_in).assert_ok()

    mod_sum = z3.URem(x_in + y_in, gate.p)
    if gate.is_controlled:
        ctrl_in = ver.input_vars[2]
        ctrl_out = ver.output_vars[2]
        ver.verify_spec(ctrl_in == ctrl_out).assert_ok()
        ver.verify_spec(y_out == z3.If(ctrl_in == 1, mod_sum, y_in)).assert_ok()
    else:
        ver.verify_spec(y_out == mod_sum).assert_ok()

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()


def _rotate_left(x: list[Qid]) -> Iterator[cirq.Operation]:
    for i in range(len(x) - 1, 0, -1):
        yield cirq.SWAP(x[i], x[i - 1])


class ModDbl(PermutationGate):
    """Computes x := (2*x)%p.

    Reference: https://arxiv.org/pdf/1706.06752 (fig.4).
    """

    def __init__(self, n: int, p: int):
        assert p % 2 == 1
        assert 0 <= p < 2**n
        self.n = n
        self.p = p

        # Prepare gates.
        self.adder2 = ConstAdder(n + 1, 2 ** (n + 1) - self.p)
        self.adder3 = ConstAdder(n, self.p, is_controlled=True)

    @property
    def input_sizes(self) -> list[int]:
        return [self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return 1 + max(self.adder2.ancilla_size, self.adder3.ancilla_size)

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        qubits = list(qubits_seq)
        n = self.n
        x, carry, anc = qubits[0:n], qubits[n], qubits[n + 1 :]

        # Step 1. Multiply by 2 by bit shift.
        yield from _rotate_left(x + [carry])

        # Step 2. "-p".
        yield self.adder2.on(*(x + [carry] + anc[: self.adder2.ancilla_size]))

        # Step 3. Controlled "+p".
        yield self.adder3.on(*(x + [carry] + anc[: self.adder3.ancilla_size]))

        # Step 4. Uncompute carry (with CNOT).
        yield CNOT(x[0], carry)
        yield X(carry)


def verify_mod_dbl(gate: ModDbl):
    ver = GateVerifier(gate)
    x_in = z3.ZeroExt(1, ver.input_vars[0])
    x_out = z3.ZeroExt(1, ver.output_vars[0])

    ver.add_precondition(z3.ULT(x_in, gate.p))

    ver.verify_spec(x_out == z3.URem(2 * x_in, gate.p)).assert_ok()

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()


class ModMul(PermutationGate):
    """Computes (x,y,z) := (x,y,(x*y)%p).

    Reference: https://arxiv.org/pdf/1706.06752 (fig.5).
    """

    def __init__(self, n: int, p: int):
        assert p % 2 == 1
        assert 0 <= p < 2**n
        self.n = n
        self.p = p

        # Prepare gates.
        self.mod_adder = ModAdder(n, p, is_controlled=True)
        self.mod_dbl = ModDbl(n, p)

    @property
    def input_sizes(self) -> list[int]:
        return [self.n, self.n, self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return max(self.mod_adder.ancilla_size, self.mod_dbl.ancilla_size)

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        n = self.n
        qubits = list(qubits_seq)
        x, y, z, anc = qubits[0:n], qubits[n : 2 * n], qubits[2 * n : 3 * n], qubits[3 * n :]
        for i in reversed(range(0, n)):
            yield self.mod_adder.on(*(y + z + [x[i]] + anc[: self.mod_adder.ancilla_size]))
            if i != 0:
                yield self.mod_dbl.on(*(z + anc[: self.mod_dbl.ancilla_size]))


def verify_mod_mul(gate: ModMul):
    ver = GateVerifier(gate)
    n = gate.n
    x_in, y_in, z_in = ver.input_vars
    x_out, y_out, z_out = ver.output_vars
    ver.add_precondition(z3.ULT(x_in, gate.p))
    ver.add_precondition(z3.ULT(y_in, gate.p))
    ver.add_precondition(z_in == 0)

    ver.verify_spec(x_out == x_in).assert_ok()
    ver.verify_spec(y_out == y_in).assert_ok()

    expected = z3.URem(z3.ZeroExt(n, x_in) * z3.ZeroExt(n, y_in), gate.p)
    ver.verify_spec(z3.ZeroExt(n, z_out) == expected).assert_ok()

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()


class ModSquare(PermutationGate):
    """Computes (x,0) -> (x,(x*x)%p).

    Reference: https://arxiv.org/pdf/1706.06752 (fig.6).
    """

    def __init__(self, n: int, p: int):
        assert p % 2 == 1
        assert 0 <= p < 2**n
        self.n = n
        self.p = p

        # Prepare gates.
        self.mod_adder = ModAdder(n, p, is_controlled=True)
        self.mod_dbl = ModDbl(n, p)

    @property
    def input_sizes(self) -> list[int]:
        return [self.n, self.n]

    @cached_property
    def ancilla_size(self) -> int:
        return 1 + max(self.mod_adder.ancilla_size, self.mod_dbl.ancilla_size)

    def _decompose_(self, qubits_seq: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        qubits = list(qubits_seq)
        n = self.n
        x, ans, x_copy, anc = qubits[0:n], qubits[n : 2 * n], qubits[2 * n], qubits[2 * n + 1 :]

        for i in reversed(range(0, n)):
            yield CNOT(x[i], x_copy)
            yield self.mod_adder.on(*(x + ans + [x_copy] + anc[: self.mod_adder.ancilla_size]))
            yield CNOT(x[i], x_copy)
            if i != 0:
                yield self.mod_dbl.on(*(ans + anc[: self.mod_dbl.ancilla_size]))


def verify_mod_square(gate: ModSquare):
    ver = GateVerifier(gate)
    n = gate.n
    x_in, ans_in = ver.input_vars
    x_out, ans_out = ver.output_vars
    ver.add_precondition(z3.ULT(x_in, gate.p))
    ver.add_precondition(ans_in == 0)

    ver.verify_spec(x_out == x_in).assert_ok()

    expected = z3.URem(z3.ZeroExt(n, x_in) * z3.ZeroExt(n, x_in), gate.p)
    ver.verify_spec(z3.ZeroExt(n, ans_out) == expected).assert_ok()

    ver.verify_ancillas().assert_ok()
    ver.verify_and_gates().assert_ok()
