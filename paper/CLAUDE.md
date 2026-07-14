# paper/ — scoped norms

Phase E workspace (weeks 7–8). Until then this directory holds `claims.md` — the claims
traceability ledger — which is live from day one.

Rules:

- **`claims.md` maps every claim → evidence.** Each of C1–C5 and each hypothesis S1–S9
  gets: status (untested / supported / refuted / mixed), the registry run_ids that bear
  on it, and the figure/table that will present it. Update it whenever a phase completes.
  A claim with no run_ids is marked `untested` — the paper may not assert it.
- **Refutations are findings.** Plan §12 commits to publishing a flat result; if S1 or S4
  come out negative, that goes in claims.md as `refuted` with the same rigor. Never
  reframe a negative into a positive by weakening the claim post hoc without a
  DECISIONS.md entry (that's a scope change the user must approve).
- Numbers in the LaTeX come from generated `\input` fragments produced from
  `results/registry.jsonl` by a script — never typed by hand.
- The leakage analysis (plan §5) and the scoping statement on extractability (plan §8)
  are commitments to state in the paper *before* review; keep them in the outline from
  the first draft.
- Genre discipline (plan §11): findings-and-methodology paper, NOT a benchmark/dataset
  paper. Artifacts (toolkit, InstBuild annotations) live in the appendix.
