import abc
from dataclasses import dataclass
from typing import Optional, Self

import cirq
import z3


class PermutationGate(cirq.Gate):
    """Cirq gate that can be verified with VeriCirq.

    This gate must satisfy the following conditions:
     * It must only consist of X, CNOT and CCNOT gates.
     * (Implied by above) It's a permutation gate - it maps basis states to basis states.
     * It acts on a fixed number of qubits. Some of the first qubits are split in 1 or more little-endian unsigned
        integer registers, and remaining qubits are the "ancilla" qubits.

    The user must specify these 3 things:
     * `input_sizes` - sizes of input registers.
     * (Optional) `ancilla_size` - number of ancilla qubits. If not specified, defaults to 0 (no anicllas).
     * Implementation of the gates by deomposing it into X, CNOT and CCNOT gates. For this, implement _decompose_
         method that takes list of qubits and returns iterator over gates. This is Cirq's convention.
    """

    @property
    @abc.abstractmethod
    def input_sizes(self) -> list[int]:
        """Returns size of each input register."""

    @property
    def ancilla_size(self) -> int:
        """Returns number of ancilla qubits."""
        return 0

    def num_qubits(self) -> int:
        return sum(self.input_sizes) + self.ancilla_size


def _bit_to_bool(bitvec_var, bit_id):
    """Extracts bit from z3.BitVec as z3.Bool."""
    return z3.Extract(bit_id, bit_id, bitvec_var) == 1


@dataclass
class VerificationResult:
    """Result of verification.

    Either "OK", in which case the spec was satisfied, or "FAIL", in which case it contains concrete counterexample -
    inputs and outputs for which spec was not satisfied.
    """

    ok: bool
    input: Optional[list[int]] = None
    output: Optional[list[int]] = None

    @staticmethod
    def ok() -> Self:
        return VerificationResult(True, None, None)

    def assert_ok(self):
        """Fails with informative message (containing counterexample) if result is FAIL."""
        if not self.ok:
            raise AssertionError(repr(self))

    def __repr__(self) -> str:
        if self.ok:
            return "OK!"
        else:
            return f"FAIL! Counterexample: input {self.input}, output {self.output}."


# Only these gates are expected to be produced by the gate decomposition.
# Note that cirq.X, cirq.CNOT and cirq.CCNOT are aliases to one of these types.
_ALLOWED_GATES = {
    cirq.X,
    cirq.CNOT,
    cirq.CCNOT,
    cirq.XPowGate,
    cirq.CXPowGate,
    cirq.CCXPowGate,
}


class GateVerifier:
    """Main entry point for gate verification.

    Typical usage (`gate` is PermutationGate):
        ver = GateVerifier(gate)
        spec = some_condition(ver.input_vars, ver_output_vars)
        ver.verify_spec(spec)
    """

    def __init__(self, gate: PermutationGate):
        self.gate = gate
        self.solver = z3.Solver()

        # This list will hold symbolic expressions for current qubit value.
        qubits = []

        # Initialize input with fresh variables.
        inputs_as_bool_vars = []
        for input_size in gate.input_sizes:
            register = [z3.FreshBool() for _ in range(input_size)]
            qubits += register
            inputs_as_bool_vars.append(register)

        # Ancilla qubits are initialized in 0 state.
        qubits += [z3.BoolVal(False) for _ in range(gate.ancilla_size)]
        assert len(qubits) == gate.num_qubits()

        # Convert each gate (X, CNOT, CCNOT) into corresponding logical gate.
        # For CNOT and CCNOT, we add a new variable representing output of target qubit after the gate application.
        cirq_qubits = cirq.LineQubit.range(gate.num_qubits())
        ops = cirq.decompose(
            gate.on(*cirq_qubits), keep=lambda op: op.gate in _ALLOWED_GATES
        )
        for op in ops:
            op_gate = op.gate
            qubit_ids = [q.x for q in op.qubits]

            if isinstance(op_gate, cirq.XPowGate) and op_gate.exponent == 1:
                assert len(qubit_ids) == 1
                gate_name = "X"
            elif isinstance(op_gate, cirq.CXPowGate) and op_gate.exponent == 1:
                assert len(qubit_ids) == 2
                gate_name = "CNOT"
            elif isinstance(op_gate, cirq.CCXPowGate) and op_gate.exponent == 1:
                assert len(qubit_ids) == 3
                gate_name = "CCNOT"
            else:
                raise ValueError(f"Unsupported gate: {gate}.")

            if gate_name == "X":
                assert len(qubit_ids) == 1
                q0 = qubit_ids[0]
                qubits[q0] = z3.Not(qubits[q0])
            elif gate_name == "CNOT":
                assert len(qubit_ids) == 2
                q0, q1 = qubit_ids
                output = z3.FreshBool()
                self.solver.add(output == z3.Xor(qubits[q0], qubits[q1]))
                qubits[q1] = output
            elif gate_name == "CCNOT":
                assert len(qubit_ids) == 3
                q0, q1, q2 = qubit_ids
                output = z3.FreshBool()
                self.solver.add(
                    output == z3.Xor(z3.And(qubits[q0], qubits[q1]), qubits[q2])
                )
                qubits[q2] = output

        # Collect variables for each output register.
        outputs_as_bool_vars = []
        offset = 0
        for input_size in gate.input_sizes:
            outputs_as_bool_vars.append(qubits[offset : offset + input_size])
            offset += input_size

        # Remember expressions representing ancillas in the end of computation.
        anc_start = sum(self.gate.input_sizes)
        self.final_ancillas = [
            qubits[i] for i in range(anc_start, anc_start + gate.ancilla_size)
        ]

        # Prepare BitVec variables to represent inputs and outputs.
        # Tie them to boolean variables.
        self.input_vars = []
        self.output_vars = []
        for i, input_size in enumerate(gate.input_sizes):
            input_var = z3.BitVec(f"in_{i}", input_size)
            self.input_vars.append(input_var)
            for j in range(input_size):
                self.solver.add(inputs_as_bool_vars[i][j] == _bit_to_bool(input_var, j))

            output_var = z3.BitVec(f"out_{i}", input_size)
            self.output_vars.append(output_var)
            for j in range(input_size):
                self.solver.add(
                    outputs_as_bool_vars[i][j] == _bit_to_bool(output_var, j)
                )

        # In case user wants to look at the circuit.
        self.circuit = cirq.Circuit(ops)

    def verify_ancillas(self) -> VerificationResult:
        """Verifies that all ancillas are released in zero states."""
        self.solver.push()

        # Add condition "any ancilla is 1" - if it's satisifed, it's a bug.
        self.solver.add(z3.Or(self.final_ancillas))

        if self.solver.check() == z3.sat:
            # Bug: found input that results in non-zero ancillas after computation.
            result = self._failed_result_from_model(self.solver.model())
        else:
            result = VerificationResult.ok()

        self.solver.pop()
        return result

    def verify_spec(self, spec):
        """Verifies user-specified condition about inputs and outputs.

        Spec must be z3 expression which states a fact about input and output variables.
        The variables can be accessed using `GateVerifier.input_vars` and `GateVerifier.output_vars`.
        """
        self.solver.push()
        self.solver.add(z3.Not(spec))

        if self.solver.check() == z3.sat:
            result = self._failed_result_from_model(self.solver.model())
        else:
            result = VerificationResult.ok()

        self.solver.pop()
        return result

    def _failed_result_from_model(self, model) -> VerificationResult:
        """Converts a model satisfying SAT problem to failed verification result with counterexample."""
        return VerificationResult(
            False,
            [model.evaluate(v).as_long() for v in self.input_vars],
            [model.evaluate(v).as_long() for v in self.output_vars],
        )
