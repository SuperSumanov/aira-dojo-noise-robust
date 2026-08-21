# Meta Kaggle exact-parent human-fork S0a input decision

Status: `S0A_PASS`. The official daily snapshot listing was identical before and after acquisition in both raw CRLF and
normalized LF form. Six CSV files totaling 8,216,765,816 bytes and the public dataset metadata are bound by SHA-256 in
`phase1/meta_kaggle_exact_parent_s0a_input_manifest.json`.

All required S0b identity columns are present. In particular, the official schema exposes
`Kernels.ForkParentKernelVersionId`, `Kernels.FirstKernelVersionId`, and
`KernelVersions.ParentScriptVersionId`; the dependency table remains explicitly excluded as a fork proxy. The outcome-table
file was downloaded and hashed, but S0a opened only its header and zero data rows. No notebook content, predictor effect,
GPU, or paid API was used.

The first acquisition attempt stopped before new-file download because the CLI's CRLF listing failed an exact-line guard.
The promoted attempt retained raw listings and compared an LF-normalized copy without changing any snapshot, identity rule,
or threshold. Receipt filename/credential scans are both zero.

Full remote receipt:
`/research/d7/spc/yzyang4/external-audits/meta-kaggle-s0a-20260821/receipts/s0a-crlf-v2`.
