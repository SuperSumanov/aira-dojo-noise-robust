# G-reuse cycle information via effective resistance

Date: 2026-09-05 Hong Kong. Frozen scientific source commit:
`6976358740943b9c3dede20c27da4a77443a7cbb`. Numeric-gate retry commit:
`782a7c7486a91d6d291569b44be714398ac7edc4`.

## Frozen estimand and gates

Within each task, define final connected components using endpoint-level `L + full G`
and verify that `L + basis G` has exactly the same partition. For every final
component touched by G, compute the Kirchhoff index and pair-averaged effective
resistance of both graphs. The producer uses nonzero Laplacian eigenvalues; the
independent verifier uses the shifted-Laplacian inverse identity.

The frozen gates were: aggregate resistance reduction at least 25%, median task
reduction at least 15%, at least 20/28 tasks with a strict positive reduction,
maximum equal-task contribution at most 20%, and exact 2745/790 edge counts with
matching partitions.

## Exact result

- aggregate basis/full Kirchhoff: `164865.8708564815` / `73638.03544197977`;
- aggregate effective-resistance reduction: `0.5533457891592195`;
- median task reduction: `0.6132619063449083`;
- tasks with strict positive reduction: 27/28;
- maximum equal-task reduction share: `0.05919087827267576`;
- all five gates: PASS;
- status: `G_REUSE_CYCLES_HAVE_BROAD_SPECTRAL_INFORMATION`.

Thus, the 1,955 full-G edges beyond the rank-preserving forest are not merely rank
redundancy on this corpus: they broadly improve the topology associated with
pairwise estimation. This supports keeping full G-reuse as the effect candidate
and treating the minimum-token basis only as a cost challenger.

## Numeric retry and verification

The first formal root completed producer A/B and verifier A/B with zero return codes
and empty stderr, but the outer runner failed because it additionally required the
two inverse-verifier JSON files to be byte-identical. Ten of 145 float fields differed;
the maximum absolute and relative differences were `1.8189894035458565e-12` and
`5.033757779443083e-16`, with zero non-float differences. Top-level PASS status was
visible during diagnosis, so the retry is explicitly post-status engineering work.

The only retry change replaced that extra byte-equality check with the
result-before `rel_tol=1e-8, abs_tol=1e-7` recursive close check. Producer A/B remained
byte-exact. In the fresh retry, verifier A/B maximum absolute difference was
`3.637978807091713e-12`; producer eig versus verifier inverse metrics differed by at
most `8.440110832452774e-10`, with zero non-float differences. All four runs returned
zero with empty stderr; durations were 52.21, 43.60, 44.45, and 43.39 seconds.

Producer receipt SHA-256 is
`c238a08cf34b3e5321cf4fe01556ceac79ee49015f0de31addf3613074a2cea5`.
Downloaded archive SHA-256 is
`585f6093539c1443d2ebd17351df08e306b53f4cd58acb982840df9ff215dd2d`.
The exact-commit eleven-file source archive had identical local/remote SHA-256
`57e947cb1fe29562f9f58a98e940ff60244f20136ec0ca698a2a974e216d61a3`.
All ten output files passed the downloaded manifest; credential and identity-key
scans had zero hits. GPU jobs, API calls, and model fits were zero.

## Claim boundary and prior work

Effective resistance is a graph proxy, not critic accuracy or an end-to-end search
gain. Neural predictors share features across endpoints, so item-parameter topology
does not guarantee the same magnitude of model benefit. Spectral comparison design
is also established prior work, including
[Osting et al., ICML 2013](https://proceedings.mlr.press/v28/osting13.html),
[Shah et al., JMLR 2016](https://jmlr.org/papers/v17/15-189.html), and
[Hendrickx et al., ICML 2019](https://proceedings.mlr.press/v97/hendrickx19a.html).
Our contribution here is the measured corpus-specific headroom and audit, not a new
spectral algorithm. Source/config/experiment closure, G0 measured cost, and explicit
GPU approval remain. No selected edge or task/run/card identity was emitted.
