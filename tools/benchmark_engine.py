"""Non-blocking benchmark for representative duels."""
from argparse import ArgumentParser
from time import perf_counter
from mordheim_combat_lab import Characteristics,DuelRequest,FighterBuild,compile_fighter,simulate_duel

def main():
    parser=ArgumentParser();parser.add_argument("-n","--simulations",type=int,default=500_000);args=parser.parse_args()
    c=Characteristics(4,4,4,2,4,2)
    first=compile_fighter(FighterBuild("mordheim",c,main_weapon_id="weapon.sword",off_hand_id="weapon.dagger",armour_id="armour.light-armour",skill_ids=("skill.mighty-blow",)))
    second=compile_fighter(FighterBuild("mordheim",c,main_weapon_id="weapon.axe",off_hand_id="defence.shield",armour_id="armour.heavy-armour"))
    start=perf_counter();result=simulate_duel(DuelRequest(first,second,args.simulations,seed=2026));elapsed=perf_counter()-start
    print(f"{args.simulations/elapsed:,.0f} simulations/s; {elapsed:.3f}s; {result}")
if __name__=="__main__":main()
