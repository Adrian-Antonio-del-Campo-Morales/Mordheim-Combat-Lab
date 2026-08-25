# Mordheim rule implementation notes

This file records deferred mechanics for the one-on-one close-combat simulator.
It is not a rules source. Canonical rules and citations live under
`sources/knowledge`.

The supported catalogue contains 49 Core and Grade 1a–1c warbands. Court of the
Profane Pleasures and all Grade 2+ warbands are deliberately excluded.

## Implemented mechanics

The engine resolves initiative and charge order, fighting with two weapons,
parries, critical hits, armour penetration, injury states, the scoped weapons
and armour, and the direct duel effects exposed by supported profiles and
skills. Rule implementations use canonical English public names.

Profile-only mechanics now represented directly include `Poisonous`, the two
`Weedy`/`Downtrodden` injury tables, `Maddened With Pain`, `Cloud of Flies`, the
melee version of `Dodgy`, `Trample`, `Charge`, natural armour, `Survivor`,
`Wight Blades`, `Perfect Killer`, and `Art of Silent Death`. Campaign and board
state clauses attached to those rules remain outside the one-on-one combat
model where they do not affect its result.

Additional implemented rules include `Step Aside`, `Shaggy Hide`,
`Horned One`, `Thick Skull`, `True Grit`, `’Eadbasher`, `Fey Quickness`, Dwarf
`Combat Master`/`Master of Blades`, `Bellowing Battle Roar`, `Ferocious Charge`,
`Monster Slayer`, `Berserker`, Norse `berserk charge`, `crushing blow`, `shield
master`, `Foul Odour`, `well ’ard`, `Hardy Constitution`, `Sign of Sigmar`, and
`savage fury` and their precise English timing restrictions.
`Expert Swordsman` now also recognises Weeping Blades, and the `No Pain` plus
`Jump Up` interaction follows the English exception instead of cancelling the
knocked-down result.

## Deliberately ignored duel edge cases

The following rules are retained in the knowledge base but are not resolved by
the duel engine:

* **TODO — optional attack framework:** `Bear Hug`, `Bull Charge`/`Bull Rush`,
  `Energy Focus`, and `Wraith Touch` are
  optional replacements for normal attacks. Choosing them correctly requires a
  per-round tactical policy and, for Bear Hug, replacing two already successful
  attacks with an opposed roll. They are too distinct for the current loadout
  model and are not silently approximated as bonus attacks.
* **TODO — only if duel scope is expanded:** `Black Hunger` and `corpse bomb`
  combine optional activation, self-inflicted
  damage, area effects, or permanent model loss. Their multi-model/turn decision
  state is outside the one-on-one optimizer.
* **TODO — only if the fighter model is expanded:** `Tail Fighting` and mounted
  or multi-part models require three weapon-bearing
  limbs or separately targetable fighters. The engine intentionally retains its
  one-model/two-hand representation.
* **TODO — out of current scope:** Leadership-controlled effects (`mesmerising dance`, `crude belch`, `Sea
  Shanty Singer`), deployment/hidden-charge bonuses, traps, falling, pushing,
  terrain-only bonuses, psychology, magic, and effects on nearby allies remain
  outside scope.
* **TODO — relevant only to multi-opponent combat:** effects that trigger only
  after defeating another opponent (`Bloodgreed`,
  `Fury of Khaine`, `sweeping blow`) cannot occur in a single-opponent duel.

Additional deferred mechanics are **TODO** `Torturer`, `Contagious`, `Master of
Runes`, `Sneaky Git`, and both `Netter` variants. They require persistent stat
loss, retaliation on elimination, once-per-battle resource tracking, deployment
state, or pre-contact net resolution respectively.


## Sources

* https://mordheimer.net/docs/rules/close-combat
* https://mordheimer.net/docs/rules/wounds-and-injuries
* https://mordheimer.net/docs/warbands
* https://mordheimer.net/docs/warbands/grade-1a-warbands/mercenaries
* https://mordheimer.net/docs/campaigns/skills
* https://mordheimer.net/docs/weapons-armour/close-combat
* https://mordheimer.net/docs/weapons-armour/armour
