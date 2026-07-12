# Super SOL v0.5 benchmark postmortem

Date: 2026-07-12  
Status: failed candidate; immutable disclosed evidence

## Result

The study produced **16 paired observations** for Terra/medium raw versus Terra/medium with Super
SOL v0.5. The paired confidence interval for the score effect was `[-4.38, +3.35]`. Full passes fell
from 9 to 8. The candidate therefore failed its preregistered direction, pass-rate, and repeated
regression requirements.

The intervention was weak rather than expensive: candidate tokens increased only 2.1%. The natural
router selected pass-through in 10 of 16 candidate runs, or **62.5%**. The remaining selections were
two concurrency, two migration, and two security routes. Failure atomicity was never selected.

T114 regressed by **-17.5** points in both repetitions. The disclosed task is not evidence by itself
that routing caused the regression, but the repeated miss makes failure-atomicity recall the first
diagnostic target. T114 and its fixture nouns must never be copied into routing signals.

T112 also showed a capability ceiling: Terra raw, Terra with v0.5, and Sol/high each scored 42.5,
while Sol/max scored 100. A short procedure cannot be assumed to substitute for higher reasoning
effort on every task.

For comparison, Fablize's observed +6.13 points used 23% more tokens, 13.7% more time, and 35.7% more
cost. This does not prove the framework is generally superior, but it shows that its improvement was
not free. Super SOL v0.6 therefore permits a bounded 15% specialist resource budget while retaining
a 3% pass-through target.

## Decision

v0.5 is not promoted. Its result is frozen, and all observed tasks are development evidence only.
v0.6 must separate routing recall from procedure effectiveness before any new performance claim.
