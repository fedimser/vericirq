# VeriCirq

VeriCirq is a small library for the formal verification of quantum arithmetic circuits.

It takes a quantum circuit (as [cirq.Gate](https://quantumai.google/reference/python/cirq/Gate)) that can be decomposed into [supported gates](https://github.com/fedimser/vericirq/blob/main/.github/skills/vericirq-circuit-implementation/SKILL.md#supported-gate-set). For such an operation, it can verify any condition about inputs and outputs **for all possible inputs**.

The library uses [cirq](https://en.wikipedia.org/wiki/Cirq) for circuit representation and [z3](https://en.wikipedia.org/wiki/Z3_Theorem_Prover) for verification.

This project was completed as part of the course "[Computer-Aided Reasoning for Software](https://courses.cs.washington.edu/courses/csep590b/26sp/)" (Spring 2026) at the University of Washington.

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

### How to run the example (for CARS final project)

```
git clone https://github.com/fedimser/vericirq.git && cd vericirq && pip install -e . && python ./example.py
```

### Examples

See [Examples.ipynb](Examples.ipynb) for a demonstration of how to use the library.

See [vericirq/examples](vericirq/examples) for more advanced examples of algorithms implemented in Cirq
and formally verified by VeriCirq. It includes implementations for: addition, 
subtraction, comparison, multiplication, division, and square root.

### AI Skill

For autonomous implementation and formal verification workflows, see the AI agent skill at [.github/skills/vericirq-circuit-implementation/SKILL.md](.github/skills/vericirq-circuit-implementation/SKILL.md).

### How it works
The quantum circuit is converted into a Boolean circuit. The user provides a spec as a Z3
expression (over BitVec variables) for inputs and outputs. Then VeriCirq constructs a
[SAT problem](https://en.wikipedia.org/wiki/Boolean_satisfiability_problem) to find any input
for which the spec is false.

* If the SAT problem has a solution, it's a bug (a spec violation), and the user gets concrete counterexamples for which the spec is violated.
* If the SAT problem is unsatisfiable, the spec holds for all inputs.

The core implementation is in [vericirq.py](vericirq/vericirq.py).


### Future work

* This is a course project, but I hope it will be useful for real research, and I plan to publish it on PyPI in Summer 2026.
