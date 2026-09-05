# Frozen WL escrow catch-up, not effect validation

2026-09-06 HK05:42. User approved in-session continuation; this is one necessary
coverage update after completed intake, not a new model or an exploratory grid.
Question: can the existing frozen WL baseline cover the new673-run snapshot while
preserving every previous517-run prediction and keeping protected truth sealed?

Matrix: one original producer, one original independent numerical verifier, one
original snapshot-chain verifier; serial single-CPU stages, all thread caps1.
0GPU,0API,0model fits,0base updates. One foreground monitor observation, not a new
scheduled/background daemon. Two-hour hard wall cap plus bounded process-group cleanup.
Expected60–95minutes from prior25:14.25+23:46.31 at517runs; not a completion guarantee.
Old artifact footprint12662947bytes; actual64MiB allocation test before launch.

The original scoring/control code, frozen bundle/activation/protocol hashes and
minimum-new-runs12 remain unchanged. Controlbc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0,
scorer031edb34400781ca026bc9833ac7f850312ffb1c; monitorSHA
4cec4fd7cb2382f6e7f4e071b31212cfa45901de9dcfcc7730f18cad4e619daa.
Prior e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d;
current cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2.
Original673-run cohort, no selection/reordering or outcome-driven subset.

13-item preflight:
1. Actual emitted matrix must bind both commits/snapshots and517→673counts.
2. Wrapper validation/refusal tests before real launch; existing scientific runner unchanged.
3. Original snapshot-chain verifier checks old-set/sequence and shared predictions.
4. Only aggregate structural coverage reported; no effect mean or sample accuracy.
5. Existing frozen selection/stratification unchanged; no metrics used for selection.
6. All escrow files, command/runtime/trace evidence retained privately.
7. No label/outcome paths; original trace/security gates required before promotion.
8. Frozen model/order/RNG; no fitting, re-selection or new seed.
9. Credential checks before any public receipt/log; no raw prediction artifacts exported.
10. Single-CPU bounded7200seconds, process-group TERM/KILL on timeout, no auto-retry.
11. Coverage only, not power/model-capacity/accuracy/scaling evidence.
12. Save actual child rc before any timestamp/printing, postcheck promotion only onzero.
13. InitialLATEST,331archives,zero config-v2 names, exact prior WL state/log and free
    lock; all prior WL PID owners absent. Unknown duplicate/output/hash drift stops.

Transition and receipt-common-support state/log hashes are checked unchanged; no
transition refit, receipt waiter or Target522 rescue starts. The old receipt and
transition PID files may reference recycled IDs; those processes are never signalled.
First960 closure remainsfalse. Agent reads only safe structural receipts, never
prediction values, accuracy, utility or candidate identities. Original protocol's
trusted numerical verifier may privately compare escrow values as already frozen.
