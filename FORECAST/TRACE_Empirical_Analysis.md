# Caribbean TRACE: empirical analysis and alignment with the original argument

## Scope and checks
The uploaded scored workbook contains 216 successfully scored controlled runs: 36 accepted true/false claim pairs, each evaluated under regional corpus, source ablation and oracle passage conditions. Each condition contains 36 supported and 36 refuted claims. The evaluator is recorded as gpt-oss:120b. All selected run IDs are unique. Open-web rows are excluded. Four of the original 40 pairs are outside this analysis.

The gold labels are those recorded in the adjudicated workbook. This analysis does not independently reverify the underlying factual sources or establish reviewer independence. The 216 rows are repeated measurements of 36 pairs, not 216 independent observations.

## Main descriptive results
| Condition | Mean E, supported | Mean E, refuted | Mean T, supported | Mean T, refuted |
|---|---:|---:|---:|---:|
| Regional corpus | 0.784 | 0.400 | 81.16 | 71.88 |
| Source ablation | 0.231 | 0.207 | 61.96 | 62.31 |
| Oracle passage | 0.609 | 0.269 | 76.53 | 65.64 |

For supported claims, mean E falls by 0.553 after target-source ablation (95% pair bootstrap interval 0.500–0.603). Mean T falls by 19.20 points (15.66–23.21). The paired Wilcoxon comparisons remain significant after Holm adjustment across the 15 exploratory comparisons. These are effects within this curated sample and this implementation.

The supported-minus-refuted E gap is 0.384 in the regional corpus and 0.024 under ablation. The ablation gap interval is −0.004 to 0.060. Its nonsignificant test does not establish equivalence. The useful conclusion is the observed reduction in separation, assessed directly in gap_reduction.csv.

E AUROC is 0.985 (95% pair bootstrap interval 0.959–1.000) for the regional corpus, 0.512 (0.471–0.554) for ablation and 0.956 (0.919–0.987) for the oracle passage. T AUROC is respectively 0.814, 0.478 and 0.812. AUROC measures ranking discrimination; it does not validate the PUBLISH threshold.

## Empty retrieval: the narrow failure described by the abstract
Ablation produces 13 empty retrievals: six supported claims and seven refuted claims. Every one receives E=0 and V=0.2. Thus these two scores cannot separate the gold classes within these empty runs. Mean T is 45.61 for supported and 45.81 for refuted claims, reflecting the remaining signals. These are different claims, not necessarily 13 matched empty pairs; the equality of E/V follows from the scoring rules.

Empty retrieval in this experiment means no passage survived this corpus/retriever setup. It does not prove that the evidence does not exist, was never produced, or that a model lacks domain competence. Eleven or more retries are not implied by this result. Treat an empty state as a retrieval/evidence-availability boundary.

## Routing reveals an additional limitation
At the existing T≥70 PUBLISH threshold:
| Condition | Supported claims published | Refuted claims published |
|---|---:|---:|
| Regional corpus | 33/36 (91.7%) | 21/36 (58.3%) |
| Source ablation | 8/36 (22.2%) | 9/36 (25.0%) |
| Oracle passage | 27/36 (75.0%) | 12/36 (33.3%) |

The false-claim publication rate is substantial even when evidence is present. Strong E ranking discrimination therefore coexists with unsuitable composite routing in this sample. The paper should report this rather than present source inclusion as sufficient for trustworthy decisions.

## Implementation audit against the presentation
The presentation describes E as the fraction of claims supported and V as independently graded verification. The submitted implementation differs: E combines 60% lexical containment and 40% LLM support, then takes the maximum passage score. For a single atomic claim, V is determined by E: 0.5E+0.2 below E=0.15, and 0.5E+0.5 otherwise, subject to rounding. Workbook agreement is within 0.0001. V therefore supplies no independent verification evidence and has identical AUROC to E.

The support prompt combines contradiction and unrelated evidence into one low category. The V code labels scores below 0.15 contradicted without explicitly establishing contradiction. Lexical overlap can raise scores for false claims that differ only in a number or name. These are plausible mechanisms to investigate using saved passage scores and evaluator responses; they are not established causal explanations from the workbook alone.

T uses E,V,L,C with S unavailable and weights renormalised. L is evaluated with the claim itself supplied as both question and answer. C measures agreement between evaluator-estimated confidence and V, not calibration against observed correctness. The paper must state these adaptations. Do not describe this run as validation of the full five-signal framework.

Regional E exceeds oracle E even for supported claims. The full corpus provides several candidate passages whereas the oracle supplies one short reviewed excerpt; a maximum over more candidates can increase E. The oracle is an evidence-availability control, not a guaranteed upper bound on score.

## Alignment with the abstract and talk
Supported empirically: authoritative-source removal can depress scores for adjudicated correct Caribbean claims; discrimination deteriorates under ablation; empty retrieval makes E/V class-insensitive under these scoring rules.

Not established: a measured Global North/Global South disparity; systematic Caribbean underrepresentation in LLM training; failure of ordinary open-web search; regional population prevalence of the problem; absence of evidence production; improved accuracy or decision utility of a domain-competence signal. There is no northern comparison group, training-data audit, or completed primary open-web evaluation here.

The presentation calls the work conceptual and the correction unvalidated. It can now describe a controlled empirical extension, while retaining these limits. Replace references to independent V grading with the actual implementation, or test a revised V separately. Retain the original scorer as the baseline. Do not retroactively change its formulas and attribute new results to this run.

## Proposed paper framing
Research question: How does target-source availability affect the scores and routing of paired supported and refuted Caribbean claims in an output-level trust scorer?

Defensible contribution: a curated paired-claim experiment showing evidence-availability dependence and a loss of discrimination under controlled source ablation, together with a transparent audit of the scorer's measurement and routing limitations.

Suggested results sentence: “Across 36 adjudicated Caribbean claim pairs, source ablation reduced mean evidence grounding for supported claims from 0.784 to 0.231 and reduced E discrimination from AUROC 0.985 to 0.512. Thirteen empty-retrieval runs received identical E and V values regardless of gold class. Composite routing nevertheless published 21 of 36 refuted claims in the regional-corpus condition, indicating an additional threshold and signal-validity limitation.”

## Methods and reproducibility
Analysis uses a fixed random seed 20260930 and 10,000 percentile-bootstrap resamples. Resampling is by claim pair; AUROC resamples both versions together. Paired score contrasts use Wilcoxon signed-rank tests with Holm adjustment across 15 exploratory comparisons. Bootstrap intervals are unadjusted pointwise intervals. Claim pairs are purposively selected, so intervals are descriptive sampling-variability summaries, not evidence of representativeness. Pairs may share sources and countries, so source-level dependence remains a limitation. There is one recorded evaluator result per input; intervals do not capture evaluator rerun variability. Shared prompt caching also creates dependent evaluator components.

## Next work before manuscript conclusions
1. Retain the scorer configuration, raw run logs and LLM prompt/response cache alongside this workbook to verify provenance and reproduce evaluator behaviour.
2. Use those logs for a focused audit of false PUBLISH decisions and oracle-versus-corpus discrepancies. Existing gold reviews need not be repeated. Passage-relation review is a different optional validation task.
3. Report the original baseline and the empty-state flag side by side. The current flag changes the label for empty retrieval; it does not establish better factual decisions or detect all cases where nonempty evidence is irrelevant.
4. If testing a revised verification or competence signal, freeze its definition before the additional run and evaluate it separately. Do not optimise thresholds and report their accuracy on these same 36 pairs without held-out validation.
