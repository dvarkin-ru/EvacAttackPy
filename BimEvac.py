import math
import json
from EvacAttackShared import points, room_area, cntr_real

class PeopleFlowVelocity(object):
    ROOM, TRANSIT, STAIR_UP, STAIR_DOWN = range(4)
    V0, A, D0 = range(3)
    PATH_VALUE = {
        ROOM: [100, 0.295, 0.51],
        TRANSIT: [100, 0.295, 0.65],
        STAIR_DOWN: [100, 0.400, 0.89],
        STAIR_UP: [60, 0.305, 0.67],
    }

    def __init__(self, projection_area: float = 0.1) -> None:
        self.projection_area = projection_area
        self.D09 = self.to_pm2(0.9)

    def to_m2m2(self, d: float) -> float:
        return d * self.projection_area

    def to_pm2(self, D: float) -> float:
        return D / self.projection_area

    @staticmethod
    def velocity(v0: float, a: float, d0: float, d: float) -> float:
        """
        Функция скорости. Базовая зависимость, которая позволяет определить скорость людского
        потока по его плотности

        Parameters
        ----------
        v0 : float
            начальная скорость потока, м./мин.
        a : float
            коэффициент вида пути
        d0 : float
            допустимая плотность людского потока на участке, чел./м2
        d : float
            текущая плотность людского потока на участке, чел./м2

        Return
        ------
        Скорость людского потока, м/мин
        """

        return v0 * (1.0 - a * math.log(d / d0))

    def speed_through_transit(self, width: float, d: float) -> float:
        """
        Функция скорости движения людского потока через проем

        Parameters
        ----------
        width : float
            ширина проема
        d : float
            плотность людского потока в элементе, для которого определяется скорость

        Return
        ------
        Скорость, м/мин
        """

        v0 = self.PATH_VALUE[self.TRANSIT][self.V0]
        d0 = self.PATH_VALUE[self.TRANSIT][self.D0]
        a = self.PATH_VALUE[self.TRANSIT][self.A]

        if d > d0:
            D = d * self.projection_area

            m = 1 if D <= 0.5 else 1.25 - 0.5 * D
            q = self.velocity(v0, a, d0, d) * D * m

            if D >= 0.9:
                q = 2.5 + 3.75 * width if width < 1.6 else 8.5

            v0 = q / D

        return v0

    def speed_in_room(self, d: float) -> float:
        """
        Parameters
        ----------
        d : float
            плотность людского потока в элементе, для которого определяется скорость

        Return
        ------
        Скорость потока по горизонтальному пути, м/мин
        """
        # Если плотность потока более 0.9 м2/м2,
        # то принудительно устанавливаем ее на уровке 0.9 м2/м2
        d = self.D09 if d >= self.D09 else d

        v0 = self.PATH_VALUE[self.ROOM][self.V0]
        d0 = self.PATH_VALUE[self.ROOM][self.D0]
        a = self.PATH_VALUE[self.ROOM][self.A]

        return self.velocity(v0, a, d0, d) if d > d0 else v0

    def speed_on_stair(self, direction: int, d: float) -> float:
        # Если плотность потока более 0.9 м2/м2,
        # то принудительно устанавливаем ее на уровке 0.9 м2/м2
        d = self.D09 if d >= self.D09 else d

        if not (direction == self.STAIR_DOWN or direction == self.STAIR_UP):
            raise ValueError(
                f"Некорректный индекс направления движеия по лестнице: {direction}. \n\
                               Индекс можети принимать значение `PeopleFlowVelocity.STAIR_DOWN` или `PeopleFlowVelocity.STAIR_UP`"
            )

        v0 = self.PATH_VALUE[direction][self.V0]
        d0 = self.PATH_VALUE[direction][self.D0]
        a = self.PATH_VALUE[direction][self.A]

        return self.velocity(v0, a, d0, d) if d > d0 else v0


class Moving(object):
    MODELLING_STEP = 0.008  # мин.
    MIN_DENSIY = 0.01  # чел./м2
    MAX_DENSIY = 5.0  # чел./м2

    def __init__(self, bim) -> None:
        self.bim = bim
        self.pfv = PeopleFlowVelocity(projection_area=0.1)
        self._step_counter = [0, 0, 0]
        self.direction_pairs = {}
        self.zones = {el["Id"]:el for lvl in self.bim['Level'] for el in lvl['BuildElement'] if el['Sign'] in ('Room', 'Staircase')}
        self.transits = {el["Id"]:el for lvl in self.bim['Level'] for el in lvl['BuildElement'] if el['Sign'] in ('DoorWayInt', 'DoorWay', 'DoorWayOut')}
        # Заполняем высоту
        for lvl in self.bim['Level']:
            for el in lvl['BuildElement']:
                if "ZLevel" not in el:
                    el["ZLevel"] = lvl["ZLevel"]
        self.lvlname = 'NameLevel' if self.bim['Level'][0].get('NameLevel') else 'Name'
        self.safety_zones = [{"Output": [key,], "ZLevel": val["ZLevel"], "NumPeople": 0.0, "Sign": "SZ", "Potential": 0.0}
                             for key, val in self.transits.items() if val['Sign'] == "DoorWayOut"]
        for t in self.transits.values():
            t["IsBlocked"] = False
            t["IsVisited"] = False
            t["NumPeople"] = 0.0
            t_points = points(t)
            t["Width"] = max(math.dist(p1,p2) for p1, p2 in zip(t_points, t_points[1:]+t_points[:1]))
        for z in self.zones.values():
            z["IsBlocked"] = False
            z["IsVisited"] = False
            z["Area"] = room_area(z)
        self.time = 0.0

    def step(self):
        self._step_counter[0] += 1
        for t in self.transits.values():
            t["IsVisited"] = False
            t["NumPeople"] = 0.0
            t["Color"] = ""
        for z in self.zones.values():
            z["IsVisited"] = False
            z["Potential"] = math.inf
            z["Color"] = ""

        zones_to_process = self.safety_zones.copy()
        self._step_counter[1] = 0

        while len(zones_to_process) > 0:
            receiving_zone = zones_to_process.pop(0)
            self._step_counter[2] = 0
            for transit in (self.transits[tid] for tid in receiving_zone["Output"]):
                if transit["IsVisited"] or transit["IsBlocked"]:
                    continue

                giving_zone = self.zones[transit["Output"][0]]
                transit_dir = 1
                if giving_zone == receiving_zone:
                    if len(transit["Output"]) < 2:
                        # TODO: do something?
                        continue
                    giving_zone = self.zones[transit["Output"][1]]
                    transit_dir = -1
                if giving_zone["IsBlocked"]:
                    continue

                moved_people = self.part_of_people_flow(receiving_zone, giving_zone, transit)
                # print(giving_zone.num_of_people, receiving_zone.num_of_people, moved_people)

                if giving_zone["NumPeople"] < moved_people:
                    print("Cut", moved_people, "to", giving_zone["NumPeople"])
                    moved_people = giving_zone["NumPeople"]
                receiving_zone["NumPeople"] += moved_people
                giving_zone["NumPeople"] -= moved_people
                transit["NumPeople"] = moved_people * transit_dir
                # self.direction_pairs[transit.id] = (giving_zone, receiving_zone)

                if receiving_zone not in self.safety_zones:
                    receiving_zone["Density"] = receiving_zone["NumPeople"] / receiving_zone["Area"]
                giving_zone["Density"] = giving_zone["NumPeople"] / giving_zone["Area"]

                giving_zone["IsVisited"] = True
                transit["IsVisited"] = True

                if len(giving_zone["Output"]) > 1 and giving_zone not in zones_to_process:  # отсекаем помещения, в которых одна дверь
                    zones_to_process.append(giving_zone)

                new_pot = self.potential(receiving_zone, giving_zone, transit["Width"])
                if new_pot < giving_zone["Potential"]:
                    giving_zone["Potential"] = new_pot
                    giving_zone["Color"] = receiving_zone.get("Color")
                    transit["Color"] = receiving_zone.get("Color")
                zones_to_process.sort(key=lambda d: d["Potential"])

                self._step_counter[2] += 1

            self._step_counter[1] += 1
        self.time += self.MODELLING_STEP

    def potential(self, rzone, gzone, twidth):
        p = math.sqrt(gzone["Area"]) / self.speed_at_exit(rzone, gzone, twidth)
        return rzone["Potential"] + p

    def speed_at_exit(self, rzone, gzone, twidth):
        # Определение скорости на выходе из отдающего помещения
        zone_speed = self.speed_in_element(rzone, gzone)
        transition_speed = self.pfv.speed_through_transit(twidth, gzone["Density"])

        return min(zone_speed, transition_speed)

    def speed_in_element(self, rzone, gzone):
        # По умолчанию, используется скорость движения по горизонтальной поверхности
        v_zone = self.pfv.speed_in_room(gzone["Density"])

        dh = rzone["ZLevel"] - gzone["ZLevel"]  # Разница высот зон
        # Если принимающее помещение является лестницей и находится на другом уровне,
        # то скорость будет рассчитываться как по наклонной поверхности
        if abs(dh) > 1e-3 and rzone["Sign"] == "Staircase":
            """Иначе определяем направление движения по лестнице
                     ______   aGiverItem
                   //                         => direction = STAIR_UP
                  //
            _____//           aReceivingItem
                 \\
                  \\                          => direction = STAIR_DOWN
                   \\______   aGiverItem
            """
            direction = self.pfv.STAIR_DOWN if dh > 0 else self.pfv.STAIR_UP
            v_zone = self.pfv.speed_on_stair(direction, gzone["Density"])

        return v_zone

    def part_of_people_flow(self, rzone, gzone, transit):
        # density_min_giver_zone = 0.5 / area_giver_zone
        min_density_gzone = self.MIN_DENSIY  # if self.MIN_DENSIY > 0 else self.pfv.projection_area * 0.5 / gzone.area

        # Ширина перехода между зонами зависит от количества человек,
        # которое осталось в помещении. Если там слишком мало людей,
        # то они переходя все сразу, чтоб не дробить их
        speedatexit = self.speed_at_exit(rzone, gzone, transit["Width"])

        # Кол. людей, которые могут покинуть помещение за шаг моделирования
        part_of_people_flow = self.change_numofpeople(gzone, transit["Width"], speedatexit)
        if gzone["Density"] <= min_density_gzone:
            if part_of_people_flow > gzone["NumPeople"]:
                print("===WTF!===")
            part_of_people_flow = gzone["NumPeople"]

        # Т.к. зона вне здания принята безразмерной,
        # в нее может войти максимально возможное количество человек
        # Все другие зоны могут принять ограниченное количество человек.
        # Т.о. нужно проверить может ли принимающая зона вместить еще людей.
        # capacity_reciving_zone - количество людей, которое еще может
        # вместиться до достижения максимальной плотности
        # => если может вместить больше, чем может выйти, то вмещает всех вышедших,
        # иначе вмещает только возможное количество.
        if rzone in self.safety_zones:
            return part_of_people_flow
        max_numofpeople = self.MAX_DENSIY * rzone["Area"]
        capacity_reciving_zone = max_numofpeople - rzone["NumPeople"]
        # Такая ситуация возникает при плотности в принимающем помещении более Dmax чел./м2
        # Фактически capacity_reciving_zone < 0 означает, что помещение не может принять людей
        if capacity_reciving_zone < 0:
            return 0.0
        else:
            return part_of_people_flow if (capacity_reciving_zone > part_of_people_flow) else capacity_reciving_zone

    def change_numofpeople(self, gzone, twidth, speed_at_exit):
        # Величина людского потока, через проем шириной twidth, чел./мин
        P = gzone["Density"] * speed_at_exit * twidth
        # Зная скорость потока, можем вычислить конкретное количество человек,
        # которое может перейти в принимющую зону (путем умножения потока на шаг моделирования)
        return P * self.MODELLING_STEP

    def set_density(self, density):
        for z in self.zones.values():
            z["Density"] = density

    def set_people_by_density(self):
        for z in self.zones.values():
            z["NumPeople"] = z["Density"] * z["Area"]


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import argparse
    parser = argparse.ArgumentParser(description='Bim modeling of evacuation')
    parser.add_argument('file', type=argparse.FileType('r'))  # file already opened by argparse
    args = parser.parse_args()

    bim = json.load(args.file)
    moving = Moving(bim)

    for dens in (0.1, 0.2, 0.3):
        szones = [(z, [0, ]) for z in moving.safety_zones]
        for zone in moving.safety_zones:
            zone["NumPeople"] = 0
        moving.set_density(dens)
        moving.set_people_by_density()
        moving.step()
        num_steps = 1
        while sum([x["NumPeople"] for x in moving.zones.values() if x["IsVisited"]]) > 0:
            for i in range(len(szones)):
                szones[i][1].append(szones[i][0]["NumPeople"])
            moving.step()
            num_steps += 1
        x = [i*moving.MODELLING_STEP*60 for i in range(num_steps)]
        plt.figure()
        plt.margins(x=0, y=0)
        plt.title("График зависимости от времени кол-ва людей в безопасных зонах при начальной плотности "+str(dens))
        plt.xlabel('t, сек')
        plt.ylabel('N, кол-во человек в зоне безопасности')
        plt.grid()
        for sz, sz_people in szones:
            plt.plot(x, sz_people, label=sz["Output"][0])
        plt.plot(x, [sum(x) for x in zip(*(sz_people for sz, sz_people in szones))], label="Интегральная кривая")
        plt.legend()
    plt.show()
