# Basic close-combat rules matrix

This audit compares only behaviour represented by Mordheim Combat Lab. Movement,
shooting, psychology, magic, campaigns, and multiplayer combats remain outside the
simulation contract.

| Rule | Mordheimer | Trollheim | Runtime decision |
|---|---|---|---|
| Roll to hit | WS comparison: 3+/4+/5+, WS 0 is hit on 2+ | Same | Shared |
| Roll to wound | Strength versus Toughness table | Same | Shared |
| Strength save modifier | Begins at Strength 4 | Same | Shared |
| Critical hit | Natural 6 unless a 6 was required; one per warrior and phase | Same | Shared |
| Injury | 1–2 knocked down, 3–4 stunned, 5–6 out | Same | Shared |
| Parry | Beat the highest hit; 6 cannot be parried; sword and buckler rerolls | Same | Shared |
| Charge and strike first | Strike-first group, then Initiative, then strike-last | Same revised wording | Shared |
| Two weapons | One additional attack, resolved with its own weapon | Same | Shared |
| Knocked-down/stunned opponents | Automatic hits/removal with no same-warrior finishing chain | Same | Shared |

No global ruleset switch is therefore required. Differences found during the merge
are scoped to a warband, profile, skill, item, cost, or source edition. Records in
the same `canonical_family` remain explicit Mordheimer/Trollheim variants whenever
their normalized gameplay data differs.

