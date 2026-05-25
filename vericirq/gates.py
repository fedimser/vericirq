"""VeriCirq's own gate definitions.

These gates are wrappers around Cirq gates but have additional conditions.
Using these gates in circuits allows VeriCirq to verify these conditions.
"""

from typing import Iterator, Sequence

import cirq


class AndGate(cirq.Gate):
    """Logical AND gate, as defined in https://arxiv.org/pdf/1709.06648.

    It is equivalent to CCNOT, but has additional precondition: target is 0 before gate application.
    Using this gate instead of CCNOT allows us to verify this condition.
    """

    def num_qubits(self) -> int:
        return 3

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        assert len(qubits) == 3
        yield cirq.CCNOT(qubits[0], qubits[1], qubits[2])


class InverseAndGate(cirq.Gate):
    """Inverse logical AND gate, as defined in https://arxiv.org/pdf/1709.06648.

    It is equivalent to CCNOT, but has additional postcondition: target is 0 after gate application.
    Using this gate instead of CCNOT allows us to verify this condition.
    """

    def num_qubits(self) -> int:
        return 3

    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]:
        assert len(qubits) == 3
        yield cirq.CCNOT(qubits[0], qubits[1], qubits[2])


AND = AndGate()
IAND = InverseAndGate()
