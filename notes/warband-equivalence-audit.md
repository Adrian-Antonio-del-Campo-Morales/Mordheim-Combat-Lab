# Warband Equivalence Audit

Reviewed: 2026-08-25.

The 83 source records (49 Mordheimer and 34 Trollheim) contain 21 shared
canonical families. `canonical_family` is the identity key: translated names,
plurals, and setting prefixes do not create a separate warband.

## Movement-unit convention

Mordheimer source profiles store Movement (`M`) in inches; Trollheim profiles
store it in centimetres. They are the same game values, not different profile
statistics. The runtime normalizes Trollheim movement to inches for comparison
and formats the value for the selected UI language.

| Inches (English UI) | Centimetres (Spanish UI) |
| --- | --- |
| 2\" | 5 cm |
| 3\" | 8 cm |
| 4\" | 10 cm |
| 5\" | 12 cm |
| 6\" | 15 cm |
| 9\" | 22 cm |

The known printed profile values use the table above (including 5\" = 12 cm).
Other values use 1\" = 2.5 cm and round half centimetres up. Dice movement is
converted per die: 2D6\" = 5D6 cm.

## Re-audit after movement normalization

Movement-only mismatches no longer count as a profile difference. A strict
comparison of characteristics, cost, equipment-list references, skill access,
and rule count now identifies five additional exact profile matches:

| Canonical family | Newly matching profile | Remaining distinction |
| --- | --- | --- |
| `cult-of-the-possessed` | The Possessed / Poseído | Source-specific equipment and rule structure. |
| `dark-elves` | Cold One Beasthounds / Bestia Gélida | Source-specific equipment and rule structure. |
| `orc-mob` | Troll / Troll | Source-specific equipment and rule structure. |
| `skaven-clan-eshin` | Rat Ogre / Rata Ogro | Source-specific equipment and rule structure. |
| `skaven-clan-pestilens` | Rat Ogre / Rata Ogro | Source-specific equipment and rule structure. |

All 21 families still have non-unit differences at warband or profile level, so
they remain explicit source variants.

No source record was removed. This preserves source-specific roster limits,
equipment legality, costs, and rules while preventing centimetres and inches
from being mistaken for a gameplay difference.
