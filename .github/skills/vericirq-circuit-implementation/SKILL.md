---
name: vericirq-circuit-implementation
description: Implement reversible arithmetic quantum circuits as Cirq PermutationGate classes and verify them formally with VeriCirq. Use for porting from Q#, implementing from papers, or coding from informal user specs.
---

# VeriCirq Circuit Implementation Skill

This skill defines an autonomous workflow for implementing arithmetic quantum circuits in Cirq and proving correctness with VeriCirq.

Use this skill when the user asks to:
- port a reversible arithmetic circuit from Q# or another language,
- implement a circuit from a paper,
- implement from an informal textual spec,
- debug/fix an existing reversible circuit with formal counterexamples,
- add scalable formal tests for a gate family.

Do not use this skill for:
- non-reversible algorithms,
- circuits requiring gates outside X/CNOT/CCNOT in the final decomposition,
- pure simulation-only testing when formal verification is explicitly required.

## 1) Foundations

### 1.1 Reversible arithmetic and permutation gates

In this project, a valid circuit is modeled as a permutation gate:
- Basis-state input maps to basis-state output.
- Decomposition uses only X, CNOT, and CCNOT.
- Qubits are partitioned into little-endian unsigned integer input registers, then ancillas.
- Ancillas are assumed initialized to |0> and must be returned to |0>.

This model is strict and intentional: it enables symbolic reasoning over all possible inputs.

### 1.2 VeriCirq model (how verification works)

VeriCirq translates a Cirq decomposition into symbolic constraints:
- Each input bit is a fresh Boolean variable.
- Each X/CNOT/CCNOT updates symbolic state of the target qubit.
- Input/output registers are tied to z3 BitVec variables.
- The solver checks if any counterexample violates your spec.

Key implications:
- Specifications are over BitVec arithmetic (modular by register width).
- Unsupported gate variants are rejected.
- Ancilla checks are separate and mandatory.

## 2) Standard Implementation Workflow (Spec-first)

Follow this exact order.

### Step A: Declare gate shell

Create a gate class inheriting vericirq.PermutationGate.

Requirements:
- Add a precise docstring describing:
  - mathematical action on registers,
  - register ordering and endianness,
  - preconditions (for example, output register must start at 0),
  - source/reference (paper URL or source implementation path).
- Constructor accepts all size/shape/algorithm parameters.
  - If all registers share one size, use n.
  - If asymmetric, use explicit parameters (for example n1, n2).
- Override input_sizes.
- Override ancilla_size.
  - If unknown at first, keep a TODO placeholder and derive later.
- Add initial _decompose_ that yields empty decomposition:
  - yield from []

### Step B: Write formal specification function

Create verify_<gate_name>(gate_instance) and make it the single source of truth.

Checklist:
- Construct GateVerifier.
- Read input and output vars.
- Add preconditions with add_precondition only when needed.
  - Example: result register must be zero on input.
- Add output conditions.
  - Usually one condition per output register.
  - Use BitVec arithmetic and zero/sign extension when widths differ.
- Always include verify_ancillas.
- Use assert_ok on each required property in test-oriented verification helpers.

At this stage, keep implementation empty and run the test once.
Expected outcome: at least one spec condition fails with a counterexample.
If instead you get structural errors (unsupported gates, wrong qubit count, exceptions), fix setup before implementing algorithm logic.

### Step C: Add a minimal test entrypoint

Create or extend pytest tests:
- Add one small baseline case first (for example size 4 per register).
- Call verify_<gate_name>(gate).
- Use pytest.mark.parametrize even for one case to simplify scaling later.

### Step D: Implement decomposition

Implement algorithm incrementally in _decompose_.

Implementation rules:
- Preserve exact register slicing and ancilla layout.
- Match source algorithm step ordering unless a proven equivalent rewrite is deliberate.
- Keep helpers pure and composable (for example round functions).
- Re-check ancilla accounting whenever helper workspace changes.
- Prefer clarity over micro-optimization first; optimize after proof passes.

### Step E: Run targeted verification and debug

Run the narrow test repeatedly:
- pytest path/to/test::test_name[params]

If verification fails:
- Read failed property and counterexample inputs/outputs.
- Reproduce with simulation helper when useful:
  - vericirq.simulation.simulate_gate_on_inputs
- Compare expected vs actual per register.
- Debug indexing/endian/off-by-one/ancilla release first.
- Rarely, the formal spec may be wrong; update it only with clear justification.

### Step F: Expand coverage conservatively

After baseline passes, add more parameter sets gradually.

Guidance:
- Add cases one by one.
- Re-run tests after each addition.
- For gates with extra algorithm parameters (for example window sizes), vary them too.
- Keep runtime practical for z3.

Sizing guidance (rule of thumb):
- Linear-ish circuits: total qubits around O(100) can be reasonable.
- Quadratic-ish circuits (for example multipliers): be conservative.
  - Often keep per-register sizes around <= 10 for routine CI checks.
- Target verification runtime on the order of a few seconds per test, not minutes.

## 3) Porting from Q# (Primary Mode)

Use this process for Q# to Cirq translation.

### 3.1 Map structure first

Before coding:
- Identify top-level operation(s) to port.
- Separate helper ops/functions from core algorithm.
- List external dependencies imported from utility modules.
- Decide whether to inline tiny helpers or re-implement local helpers in Python.

### 3.2 Translate semantics, not syntax

Map Q# constructs carefully:
- Qubit[] slices are little-endian register segments; preserve exact ranges.
- for ranges:
  - a..b maps to inclusive range in Q#, exclusive in Python range.
  - descending loops a..-1..b map to range(a, b - 1, -1).
- within/apply often means compute/uncompute pattern.
  - In Cirq, emit forward ops then emit inverse/uncompute sequence.
- Adj + Ctl in Q# indicates reversibility/control support.
  - In this project, you usually emit explicit X/CNOT/CCNOT sequences.

### 3.3 Workspace and ancilla derivation

Q# use statements often define hidden workspace requirements.
Derive ancilla_size from:
- explicit temporary registers,
- helper workspaces (for example carry-lookahead work arrays),
- always ensure released cleanly by spec.

### 3.4 Typical translation pitfalls

- Off-by-one in sliced windows for shifted additions/multiplications.
- Misinterpreting inclusive Q# range bounds.
- Wrong control/target argument order in CNOT or CCNOT.
- Losing uncomputation (ancillas not zero at end).
- Introducing disallowed Cirq gate forms during inversion.
  - Important: GateVerifier accepts X/CNOT/CCNOT with exponent 1 only.
  - For self-adjoint gates, prefer reversing operation order rather than generating inverse-powered gates.

### 3.5 Validation loop for Q# ports

- Confirm decomposition has only allowed gates.
- Verify all register properties.
- Verify ancilla cleanup.
- Add at least one nontrivial parameter/size extension case.

## 4) Other Implementation Modes (Extensible sections)

This skill is organized to support more modes over time.
Future sections should be added under this chapter:
- Porting from other languages.
- Adapting an already-existing Cirq circuit to PermutationGate form.
- Implementing directly from paper pseudocode.
- Implementing from informal user specs.

When adding a new mode:
- Include a concrete checklist.
- List mode-specific pitfalls.
- Include at least one small template example.

## 5) Debugging Playbook

When test fails, debug in this order:
1. Structural setup:
- num_qubits matches register + ancilla layout.
- input_sizes and constructor parameters align with decomposition slices.
2. Allowed gates:
- only X/CNOT/CCNOT (no unsupported exponent variants).
3. Spec consistency:
- preconditions are correct and minimal.
- output equations use correct BitVec widths.
4. Functional indexing:
- register slice boundaries,
- loop bounds and direction,
- control/target orientation.
5. Ancilla lifecycle:
- all temporary computation has matching uncomputation.

Use counterexamples as first-class debugging data, not as noise.

## 6) Testing and Performance Policy

Testing strategy:
- Start with one small case to validate pipeline.
- Expand to representative sizes and parameter combinations.
- Prefer pytest parameterization.

Performance strategy:
- Keep formal tests deterministic and bounded.
- Scale inputs until confidence is good but runtime remains practical.
- If a larger case times out, keep it out of default test suite or reduce size.

## 7) Definition of Done

A gate implementation is done only when all are true:
- Formal verification function exists and is complete.
- Preconditions are explicitly encoded where required.
- All output register properties pass with assert_ok.
- Ancilla cleanup passes.
- Tests cover baseline plus additional representative sizes/params.
- Documentation states behavior, register layout, and preconditions clearly.
- Attribution requirements in section 8 are satisfied.

## 8) Attribution Requirements (Mandatory)

Every generated or heavily AI-assisted implementation must include attribution in code comments or a docstring.

Required attribution fields:
- State that the implementation was AI-generated or AI-assisted.
- Include tool name (for example: GitHub Copilot) when available.
- Include model name when available.

If the implementation is a port from a publicly available source (for example GitHub, public repo, or paper code):
- Include a direct URL to the exact source file or reference used.
- Prefer stable deep links (specific path; commit-pinned link when practical).

Recommended placement:
- In the main gate class docstring or immediately above the implementation.
- Keep attribution concise and factual.

## 9) Skill Reliability and Conflict Handling (Mandatory)

This skill is AI-assisted documentation and may contain errors, especially in domain-specific quantum details.

When implementing a circuit, if you suspect any part of this skill is incorrect (for example, it contradicts trusted source comments/specs, or following it causes a bug/counterexample), you must:
- Explicitly tell the user that the skill may be wrong in that specific part.
- Point to the exact section/bullet in this SKILL.md that caused the issue.
- Describe the observed problem caused by following that guidance.
- Propose a concrete fix to the skill text.
- Update SKILL.md only according to user instructions/approval.

Do not silently override conflicting skill guidance without informing the user.

## 10) Skill Self-Maintenance (Mandatory)

If you discover a reusable pitfall, optimization, or workflow improvement while implementing/debugging:
- Update this SKILL.md in the same change when appropriate.
- Keep additions concise (1-4 bullets or a short paragraph).
- Place updates in the most relevant section:
  - section 3.4 for translation pitfalls,
  - section 5 for debugging lessons,
  - section 6 for testing/performance guidance,
  - section 4 if it introduces a new implementation mode.
  - section 8 for attribution/provenance policy improvements.
  - section 9 for skill reliability and conflict-handling policy improvements.

Do not add long narratives or one-off case history. Capture only reusable guidance.
