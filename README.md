# VeriCirq

VeriCirq is a small library for formal verification of quantum arithmetic circuits.

It takes a quantum circuit (as [cirq.Gate](https://quantumai.google/reference/python/cirq/Gate)) that can be decomposed into X, CNOT, CCNOT gates. For such an operation, it can verify any condition about inputs and ouputs **for all possible inputs**.

The library uses [cirq](https://en.wikipedia.org/wiki/Cirq) for circuit representation and [z3](https://en.wikipedia.org/wiki/Z3_Theorem_Prover) for verification.

This project was done as a course project for a course "[Computer-Aided Reasoning for Software](https://courses.cs.washington.edu/courses/csep590b/26sp/)" (spring 2026 quarter) at University of Washington.

### Installation

To install as a Python library:

```
pip install git+https://github.com/fedimser/vericirq
```

To download for development: 

```
git clone https://github.com/fedimser/vericirq.git 
cd vericirq 
pip install -e .[dev]
pytest vericirq
```

### Examples

See [Examples.ipynb](Examples.ipynb) for examples.

### AI Skill

For autonomous implementation and formal verification workflows (including Q# porting), see the Copilot skill at [.github/skills/vericirq-circuit-implementation/SKILL.md](.github/skills/vericirq-circuit-implementation/SKILL.md).

### How it works
The quantum circuit is converted to boolean circuit. User provides a spec as z3 expression (over BitVec variables) for inputs and outputs. Then VeriCirq constructs a [SAT problem](https://en.wikipedia.org/wiki/Boolean_satisfiability_problem) to find any input on which the spec is false. 

* If SAT problem has solution - it's a bug (spec violation), and user gets concrete counterexamples on which the spec is violated.
* If SAT problem is not satisfiable - spec holds for all inputs.

The core implementation is in [vericirq.py](vericirq/vericirq.py).


### Future work

* I plan to add support for AND and IAND gates introduced in [this paper](https://arxiv.org/abs/1709.06648). These are almost the same as CCNOT, except AND has precodition (traget=0), and IAND has postocndition (target=0).
* This is course project, but I hope this will be useful for real research, and I plan to publish this on PyPi sometime in summer 2026.
