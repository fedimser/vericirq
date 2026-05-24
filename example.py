"""
End-to-end example for project milestone for CARS course.
This example defines a quantum circuit (Cuccaro Adder) and formally verifies 4 conditions for this circuit.
Please see Examples.ipynb for more detailed examples with walkthrough.

To run this example from scratch (assuming you have python and pip):

git clone https://github.com/fedimser/vericirq.git && cd vericirq && pip install -e . && python ./example.py
"""

from cirq import CNOT, CCNOT
import z3

from vericirq import GateVerifier, PermutationGate


### The code below defines adder circuit which we are going to verify.
### This circuit computes: (a, b, z) := (a, (a+b)%(2^n), z⊕(a+b)/(2^n)).
### Reference: https://arxiv.org/pdf/quant-ph/0410184
def maj(a, b, c):
    yield CNOT(c, a)
    yield CNOT(c, b)
    yield CCNOT(a, b, c)


def uma(a, b, c):
    yield (CCNOT(a, b, c),)
    yield CNOT(c, a)
    yield CNOT(a, b)


class CuccaroAdder(PermutationGate):
    def __init__(self, n: int):
        self.n = n

    @property
    def input_sizes(self):
        # First addend, second addend, carry.
        return [self.n, self.n, 1]

    @property
    def ancilla_size(self):
        return 1

    def _decompose_(self, qubits):
        n = self.n
        assert len(qubits) == 2 * n + 2
        a, b, z, c = qubits[0:n], qubits[n : 2 * n], qubits[2 * n], qubits[2 * n + 1]

        yield from maj(c, b[0], a[0])
        for i in range(1, n):
            yield from maj(a[i - 1], b[i], a[i])
        yield CNOT(a[n - 1], z)
        for i in range(n - 1, 0, -1):
            yield from uma(a[i - 1], b[i], a[i])
        yield uma(c, b[0], a[0])


### Prepare to verify CuccarroAdder of two 32-bit numbers.
adder = CuccaroAdder(32)
ver = GateVerifier(adder)
a_in, b_in, z_in = ver.input_vars
a_out, b_out, z_out = ver.output_vars
print(f"Verifying {adder.n}-bit Cuccarro adder...")

### Now verify 4 formal specifications (conditions that must be true for any input).
spec1 = a_out == a_in
print("1. First register is unchanged: ", ver.verify_spec(spec1))

spec2 = b_out == (a_in + b_in)
print("2. Second input contains the sum modulo 2^n: ", ver.verify_spec(spec2))

overflow = z3.Not(z3.BVAddNoOverflow(a_in, b_in, False))
spec3 = (z_in != z_out) == overflow
print("3. Carry bit is flipped iff overflow happened: ", ver.verify_spec(spec3))

print("4. Ancillas are returned in zero state: ", ver.verify_ancillas())
