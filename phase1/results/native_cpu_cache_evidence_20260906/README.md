# Actual native CPUAdam restart diagnosis and helper validation

Engineering evidence only, not critic/scaling benefit or production GPU qualification.

Pinned diagnosis source1b6b8372b83f68038bf964547bf4b6e8b7e2c661 compared uninterrupted,
ordinary restore and empty-tensor cache replay at four fixed(end,cut) pairs:
(4,2),(4,3),(9,7),(33,31). Ordinary restore differed at two cuts (133 and192 FP32
elements), while the other two already matched. Replay matched in all four.
Native CPUAdam has private bias-power/step caches absent from its Python state_dict;
replaying empty tensors reconstructs that cache without a Python optimizer step.

The production helper at30f179505af15ca81862d5448e820739b76a13c8 separately passed
A/B across all four cases, including unchanged parameters/moments/RNG and duplicate
restore rejection. Independent inspection verifies the exact18-file source closure,
original trace hashes and no credential/protected-path marker hits.

Important limitation: these CPU comparisons use torch.equal, not signed-zero-sensitive
byte equality. Actual GPU fingerprint and independently decoded payload byte equality
remain required. The later GPU trial is separate; this bundle does not accept it.

Original14 files imported byte-for-byte (MANIFEST covers13 members).
Helper result:75cb6581e3016ab259c35df06a69eb19cbcecd0e9272025dc631b743064b75f9.
Independent receipt:ba7e811a397fbb246fc5ca85a624daa88c9e853af48545184750b87fe7041184.
Archive:b3afb1adea874e549d64bf1dd9022645640cce41e34b90280d7607a945c4798e.
Full traces and compiled native libraries remain remote; their hashes are recorded.
