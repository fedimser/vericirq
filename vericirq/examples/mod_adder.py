from typing import Iterator, Sequence

import cirq
import z3
from cirq import CCNOT, CNOT

from ..vericirq import GateVerifier, PermutationGate



class ModAdder(PermutationGate):
    """Addition of 2 numbers modulo constant.

    Computes (x, y) := x, ((x+y)%p).

    Reference: https://eprint.iacr.org/2026/106.pdf (fig.3).

    Uses Draper adder for addition/subtraction and Cuccaro comparator for comparison.
    """

    def __init__(self, n: int, p:int):
        self.n = n
        self.p = p

    @property
    def input_sizes(self) -> list[int]:
        if self.is_controlled:
            return [1, self.n, self.m]
        else:
            return [self.n, self.m]

    @property
    def ancilla_size(self) -> int:
        x_eff_len = self.m - 1 if self.m - self.n >= 2 else self.n
        padding_len = max(self.m - self.n - 1, 0)
        carries_len = x_eff_len if x_eff_len > 1 else 0
        ctrl_len = 1 if self.is_controlled else 0
        return padding_len + carries_len + ctrl_len
    
    def _decompose_(self, qubits: Sequence[cirq.Qid]) -> Iterator[cirq.OP_TREE]: