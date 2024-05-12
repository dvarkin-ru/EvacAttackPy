from BimEvac import Moving
from BimIntruder import Intruder

class EvacAttackModel:
    def __init__(self, json_bim):
        self.bim = json_bim
        self.moving = Moving(json_bim)
        self.moving.active = True
        self.intruder = None
        
    def set_intruder(self, door, precalculate_path, intruder_type, intruder_speed):
        self.intruder = Intruder(self.bim, door, precalculate_path, intruder_type, intruder_speed)
        i_room = self.intruder.bim_curr_path[-1]["Id"]
        self.intruder.victims = self.moving.zones[i_room]["NumPeople"]
        self.moving.zones[i_room]["NumPeople"] = 0
        self.moving.zones[i_room]["Density"] = 0
        self.moving.zones[i_room]["IsBlocked"] = True
        
    def step(self):
        if self.moving.active:
            self.moving.step()
        else:
            self.moving.time += self.moving.MODELLING_STEP
        if self.intruder and self.intruder.path_len()/self.intruder.speed < self.moving.time:
            self.intruder.step_next()
            i_room = self.intruder.bim_curr_path[-1]["Id"]
            self.moving.zones[i_room]["IsBlocked"] = False
            i_room = self.intruder.bim_curr_path[-1]["Id"]
            self.moving.zones[i_room]["IsBlocked"] = True
            self.intruder.victims += self.moving.zones[i_room]["NumPeople"]
            self.moving.zones[i_room]["NumPeople"] = 0
            self.moving.zones[i_room]["Density"] = 0


