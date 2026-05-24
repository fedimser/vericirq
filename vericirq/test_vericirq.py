from .examples.cuccarro_adder import CuccaroAdder, verify_cuccaro_adder
from .vericirq import GateVerifier, PermutationGate
import pytest
import cirq


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


@pytest.mark.parametrize("n", [4, 32])
def test_verify_cuccarro_adder(n: int):
    adder = CuccaroAdder(n)
    verify_cuccaro_adder(adder)
