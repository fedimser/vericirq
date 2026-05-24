import cirq

from .vericirq import PermutationGate
from typing import Any


def _bits_to_int(bits: Any) -> int:
    return sum([int(bit) * (1 << i) for i, bit in enumerate(bits)])


def _int_to_bits(value: int, size: int) -> list[bool]:
    assert 0 <= value < 2**size
    return [(value >> i) % 2 == 1 for i in range(size)]


def simulate_gate_on_inputs(gate: PermutationGate, inputs: list[int]) -> list[int]:
    """For given gate and inputs, prduces output using simulator.

    Also verifies that ancillas are returned in 0 state.
    This function is not needed for formal verification. It's added for debugging and usage in examples.
    """
    assert len(inputs) == len(gate.input_sizes)

    # Allocate qubits.
    qubits = cirq.LineQubit.range(gate.num_qubits())

    # Write input uisng X gates.
    ct = cirq.Circuit()
    offset = 0
    for i, input_size in enumerate(gate.input_sizes):
        bits = _int_to_bits(inputs[i], input_size)
        register = qubits[offset : offset + input_size]
        for bit_id, bit in enumerate(bits):
            if bit:
                ct += cirq.X(register[bit_id])
        offset += input_size

    # Apply gate under test.
    ct += gate.on(*qubits)

    # Add measurment for every qubit.
    ct += cirq.measure(*qubits, key="m")

    # Simulate the circuit.
    sim = cirq.Simulator()
    measured = sim.simulate(ct).measurements["m"]

    # Convert measurment result to integers.
    ans = []
    offset = 0
    for input_size in gate.input_sizes:
        ans.append(_bits_to_int(measured[offset : offset + input_size]))
        offset += input_size

    # Verify ancillas were measured in |0> state.
    for anc_qubit_id in range(offset, offset + gate.ancilla_size):
        assert measured[anc_qubit_id] == False, f"Qubit {anc_qubit_id} released in non-zero state"

    return ans
