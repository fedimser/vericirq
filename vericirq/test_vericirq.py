import cirq
import pytest

from .examples.const_adder import ConstAdder, verify_const_adder
from .examples.cuccaro_adder import CuccaroAdder, verify_cuccaro_adder
from .examples.cuccaro_compare import CuccaroCompare, verify_cuccaro_compare
from .examples.divide import (
    DivideNonRestoringGate,
    DivideRestoringGate,
    verify_divide_non_restoring_gate,
    verify_divide_restoring_gate,
)
from .examples.draper_adder import DraperAdder, verify_draper_adder
from .examples.gidney_adder import GidneyAdder, verify_gidney_adder
from .examples.jhha_multiplier import JhhaMultiplier, verify_jhha_multiplier
from .examples.mct_multiplier import MctMultiplier, verify_mct_multiplier
from .examples.mod_mul import (
    ModAdder,
    ModDbl,
    ModMul,
    ModSquare,
    verify_mod_adder,
    verify_mod_dbl,
    verify_mod_mul,
    verify_mod_square,
)
from .examples.square_root import SquareRoot, verify_square_root
from .examples.subtract import (
    AddSubGate,
    SubtractGate,
    verify_add_sub_gate,
    verify_subtract_gate,
)
from .gates import AND, IAND
from .vericirq import GateVerifier, PermutationGate


def test_noop():
    class NoOpGate(PermutationGate):
        input_sizes = [10]

        def _decompose_(self, _qubits):
            yield from []

    ver = GateVerifier(NoOpGate())
    assert ver.verify_spec(ver.input_vars[0] == ver.output_vars[0]).ok


def test_xor():
    class XorGate(PermutationGate):
        input_sizes = [1, 1, 1]

        def _decompose_(self, qubits):
            yield cirq.CNOT(qubits[0], qubits[2])
            yield cirq.CNOT(qubits[1], qubits[2])

    ver = GateVerifier(XorGate())
    a_in, b_in, c_in = ver.input_vars
    a_out, b_out, c_out = ver.output_vars
    ver.verify_spec(a_out == a_in)
    ver.verify_spec(b_out == b_in)
    assert ver.verify_spec(c_out == a_in + b_in + c_in).ok
    assert not ver.verify_spec(c_out == a_in + b_in).ok


def test_bitwise_negate():
    class BitwiseNegateGate(PermutationGate):
        input_sizes = [10]

        def _decompose_(self, qubits):
            for q in qubits:
                yield cirq.X(q)

    ver = GateVerifier(BitwiseNegateGate())
    ver.verify_spec(ver.output_vars[0] == ~ver.input_vars[0])


def test_ancilla_not_zero():
    class BadGate(PermutationGate):
        input_sizes = [1]
        ancilla_size = 1

        def _decompose_(self, qubits):
            yield cirq.CNOT(qubits[0], qubits[1])

    ver = GateVerifier(BadGate())
    result = ver.verify_ancillas()
    assert not result.ok
    assert result.input == [1]


def test_bad_and_gate():
    # This gate violates the AND precondition if input[2]=1.
    class BadGate(PermutationGate):
        input_sizes = [1, 1, 1]

        def _decompose_(self, qubits):
            yield AND(*qubits)

    ver = GateVerifier(BadGate())
    result = ver.verify_and_gates()
    assert not result.ok
    assert result.input[2] == 1


def test_bad_iand_gate():
    # This gate violates the IAND postcondition if input[2]=1.
    class BadGate(PermutationGate):
        input_sizes = [1, 1, 1]

        def _decompose_(self, qubits):
            yield cirq.CCNOT(*qubits)
            yield IAND(*qubits)

    ver = GateVerifier(BadGate())
    result = ver.verify_and_gates()
    assert not result.ok
    assert result.input[2] == 1


@pytest.mark.parametrize("n", [4, 32])
def test_verify_cuccarro_adder(n: int):
    adder = CuccaroAdder(n)
    verify_cuccaro_adder(adder)


@pytest.mark.parametrize("n", [4, 32])
@pytest.mark.parametrize("with_carry", [False, True])
def test_verify_draper_adder(n: int, with_carry: bool):
    adder = DraperAdder(n, with_carry=with_carry)
    verify_draper_adder(adder)


@pytest.mark.parametrize("n1,n2", [(4, 4), (4, 7)])
def test_verify_mct_multiplier(n1: int, n2: int):
    mult = MctMultiplier(n1, n2)
    verify_mct_multiplier(mult)


@pytest.mark.parametrize("n", [3, 4])
def test_verify_jhha_multiplier(n: int):
    mult = JhhaMultiplier(n)
    verify_jhha_multiplier(mult)


@pytest.mark.parametrize("n,m", [(1, 1), (1, 2), (2, 3), (4, 4), (12, 16)])
@pytest.mark.parametrize("is_controlled", [False, True])
def test_verify_gidney_adder(n: int, m: int, is_controlled: bool):
    adder = GidneyAdder(n, m, is_controlled=is_controlled)
    verify_gidney_adder(adder)


def test_verify_subtract():
    verify_subtract_gate(SubtractGate(8))


def test_verify_add_sub():
    verify_add_sub_gate(AddSubGate(8))


@pytest.mark.parametrize("n", [3, 6])
def test_verify_divide_restoring_gate(n: int):
    verify_divide_restoring_gate(DivideRestoringGate(n))


@pytest.mark.parametrize("n", [3, 6])
def test_verify_divide_non_restoring_gate(n: int):
    verify_divide_non_restoring_gate(DivideNonRestoringGate(n))


@pytest.mark.parametrize("n,ans_size", [(1, 1), (4, 2), (5, 3), (6, 4), (10, 5)])
def test_verify_square_root(n: int, ans_size: int):
    verify_square_root(SquareRoot(n, ans_size))


@pytest.mark.parametrize("n", [1, 4, 16])
@pytest.mark.parametrize("is_controlled", [False, True])
def test_cuccaro_compare(n: int, is_controlled: bool):
    verify_cuccaro_compare(CuccaroCompare(n, is_controlled=is_controlled))


@pytest.mark.parametrize("n,c", [(4, 3), (16, 10000)])
@pytest.mark.parametrize("ctrl", [False, True])
def test_add_constant(n: int, c: int, ctrl: bool):
    verify_const_adder(ConstAdder(n, c, is_controlled=ctrl))


@pytest.mark.parametrize("n,p", [(4, 11), (16, 65000)])
@pytest.mark.parametrize("ctrl", [False, True])
def test_mod_adder(n: int, p: int, ctrl: bool):
    verify_mod_adder(ModAdder(n, p, is_controlled=ctrl))


@pytest.mark.parametrize("n,p", [(4, 11), (16, 65007)])
def test_mod_dbl(n: int, p: int):
    verify_mod_dbl(ModDbl(n, p))


@pytest.mark.parametrize("n,p", [(4, 5), (4, 11)])
def test_mod_mul(n: int, p: int):
    verify_mod_mul(ModMul(n, p))


@pytest.mark.parametrize("n,p", [(4, 5), (4, 11)])
def test_mod_square(n: int, p: int):
    verify_mod_square(ModSquare(n, p))
