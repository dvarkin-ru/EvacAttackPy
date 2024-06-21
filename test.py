from EvacAttackModel import EvacAttackModel
import json
import csv

builds = [
    ["../EvacuationPy/resources/udsu_block_1.json", 0],
    ["../EvacuationPy/resources/udsu_block_2.json", 9],
    ["../EvacuationPy/resources/udsu_block_3.json", 2],]
i_res = []
for intr_type in (1, 2, 3):
    for build, door in builds:
        i_res.append([build.split("/")[-1], "нарушитель", intr_type])
        print(build.split("/")[-1], "нарушитель", intr_type)
        with open(build) as f:
            j = json.load(f)

        model = EvacAttackModel(j)
        for zone in model.moving.safety_zones:
            zone["Color"] = zone["Output"][0]

        for speed in (30, 60, 90):
            res = []
            for dens in (0.1, 0.2, 0.3):
                model.moving.set_density(dens)
                model.moving.set_people_by_density()
                model.set_intruder(door, intr_type==1, intr_type, speed)
                model.step()
                while sum([x["NumPeople"] for x in model.moving.zones.values() if x["IsVisited"]]) > 0:
                    model.step()
                res.append(model.intruder.victims)
            i_res.append([speed, *res])
            print(i_res[-1])

with open('results.csv', 'w', newline='', encoding='utf-8') as csvfile:
    reswriter = csv.writer(csvfile)
    reswriter.writerow(["Скорость нарушителя", "Плотность 0,1", "Плотность 0,2", "Плотность 0,3"])
    for i_type in i_res:
        reswriter.writerow(i_type)
