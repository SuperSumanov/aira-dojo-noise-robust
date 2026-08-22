# TF-IDF retrospective comparison-component utility

Formal status: `VALID_NO_STRONG_COMPONENT_COST_UTILITY_POSITIVE` and independently verified. This is retrospective,
accuracy-touched D&B mechanism evidence, not a frozen-test confirmation or a live-search speedup.

The exact protocol stayed fixed while two invalid attempts were retained separately: V1 assumed every parent graph was connected;
the first V2 run exposed process-hash floating-point nondeterminism. The final run used commit
`e3cffbb6ec041e9de73efe6e112f1bd9859f6e69`; fresh exact-commit tests were 14/14 focused and 823/823 full
(33 warnings), with filename/content credential scans 0/0.

On 931 test pairs / 550 parent groups / 559 identifiable comparison components / 28 tasks:

- task-macro unweighted pair accuracy: `0.5757982662586206`, task-bootstrap CI
  `[0.5079348813388992, 0.6404919021264853]`;
- task-macro raw-gap-weighted pair accuracy: `0.5834551030090183`, CI
  `[0.4949686656930697, 0.6693520122240301]`;
- weighted minus unweighted: `+0.007656836750397718`, CI
  `[-0.05766129409784135, 0.0672026866373468]`;
- comparison-component oracle-gain capture: `0.07315959014998666`, CI
  `[-0.21575761078478997, 0.31604557521269605]`;
- component top-1: `0.5150856085082018`, CI `[0.433768152581631, 0.5925650841558566]`;
- component normalized regret: `0.9268404098500135`, CI
  `[0.6829512716452883, 1.212127651949487]`.

Support gates passed (28 tasks, 559 components), but both effect gates failed: the gap-weighted CI lower bound was not strictly
above 0.5 and component-gain CI lower bound was not strictly above 0. Query cost remains strongly lower than execution
(p95 48.958 ms versus execution p50 199.627 s), but this frozen TF-IDF critic does not show robust search utility. The same
test may not be reweighted, filtered, or thresholded to rescue a positive result.

The predeclared secondary strata do not reverse the verdict. Test Improve gap-weighted accuracy was `0.6049657508514212`
with CI `[0.5029129993574336, 0.7030161608082931]`, but its component-gain CI was
`[-0.2951723243862662, 0.3792797559908769]`; Draft failed both effect gates. Dev merged gap-weighted accuracy had CI
`[0.5150162187842591, 0.7011088384750588]`, but dev component gain crossed zero and the frozen test primary failed.

Producer A/B directories and verifier A/B receipts were byte-identical. Formal summary SHA-256 is
`f740fb03bb5743b5cba381940ec64407c789aef15dbfe8c71ece4c16967b6e91`; independent receipt SHA-256 is
`517e08fd2473f3db74ccd84b41d3ccc62a3fe4cb40648e14486e9c1c4eeb7005`.
