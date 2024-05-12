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
    MIN_DENSIY = 0.1  # чел./м2
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
            t["Color"] = None
        for z in self.zones.values():
            z["IsVisited"] = False
            z["Potential"] = math.inf
            z["Color"] = None

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

                transit["Color"] = receiving_zone.get("Color")
                giving_zone["Color"] = receiving_zone.get("Color")

                giving_zone["IsVisited"] = True
                transit["IsVisited"] = True

                if len(giving_zone["Output"]) > 1 and giving_zone not in zones_to_process:  # отсекаем помещения, в которых одна дверь
                    zones_to_process.append(giving_zone)

                new_pot = self.potential(receiving_zone, giving_zone, transit["Width"])
                if new_pot < giving_zone["Potential"]:
                    giving_zone["Potential"] = new_pot
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
    import argparse
    parser = argparse.ArgumentParser(description='Bim modeling of evacuation when attack')
    parser.add_argument('file', type=argparse.FileType('r'))  # file already opened by argparse
    args = parser.parse_args()

    bim = json.load(args.file)
    # args.file.close()
    # BimComplexity(bim)  # check a building

    # density = 1.0
    # for z in wo_safety:
    #     # if '5c4f4' in str(z.id):
    #     # if '7e466' in str(z.id) or '02707' in str(z.id):
    #     z.num_of_people = density * z.area

    D_corridor_m2m2 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]  # м2/м2
    D = [i / 100 for i in range(1, 16)]
    D_cor = [d / 0.1 for d in D_corridor_m2m2]
    D_dis = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]  # ч/м2
    T_corridor = [15.0, 20.0, 25.5, 30.0, 36.4, 42.9, 52.2, 63.2, 80.0]  # сек.
    T_c_cor = [18.6, 24.0, 29.4, 35.4, 42.6, 50.4, 58.2, 66.6, 74.4]
    # T_c_3 = [886.8, 1748.4, 2602.2, 3432.0, 4229.4, 5074.2, 5919.0, 6764.4, 7609.8]
    T_dis = [55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115]
    T_c_dis = [175.20, 195.60, 214.2, 229.20, 244.20, 260.40, 273.00, 286.80, 303.60, 315.00, 330.00, 346.20, 370.20]

    times = []  # сек.

    for density in D_cor if 'corridor' in args.file.name else D_dis if 'disbuild' in args.file.name else D:
        m = Moving(bim)

        # Doors width
        #for t in m.transits.values():
            #t.width = 2.0
            #door_points = points(t)
            #print(t["Name"], max(math.dist(p1,p2) for p1, p2 in zip(door_points, door_points[1:]+door_points[:1])))

        m.set_density(density)
        m.set_people_by_density()
        for z in m.safety_zones:
            z["NumPeople"] = 0.0

##        num_of_people = 0.0
##        for z in m.zones.values():
##            print(z.num_of_people)
##            num_of_people += z["NumPeople"]

        # for z in bim.zones.values():
        #     print(f"{z}, Potential: {z.potential}, Number of people: {z.num_of_people}, Density: {z.density}")

        time = 0.0
        for _ in range(10000):
            m.step()
            # print(m.direction_pairs)
            time += Moving.MODELLING_STEP
##            for z in m.zones.values():
##                print(z, "Number of people:", z["NumPeople"])
##            for t in m.transits.values():
##                if t["Sign"] == "DoorWayOut":
##                    #pass
##                    print(t, "Number of people:", t["NumPeople"])

            nop = sum([x["NumPeople"] for x in m.zones.values() if x["IsVisited"]])
            # if nop < 10e-3:
            if nop <= 0:
                break
        else:
            print("# Error! ", end="")

        nop_sz = sum(z["NumPeople"] for z in m.safety_zones)
        print(f"Количество человек: {nop_sz:.{4}} Длительность эвакуации: {time*60:.{4}} с. ({time:.{4}} мин.)")
        print("По зонам:", *(round(z["NumPeople"]) for z in m.safety_zones))
        nop = sum([x["NumPeople"] for x in m.zones.values()])
        print("Осталось", nop)
        times.append(time * 60)


    #for i in range(len(T)):
    #    p.append(round(T_c[i] / times[i], 2))
    #print(p)

    # plot
    plot = True
    if plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        if 'corridor' in args.file.name:
            ax.plot(D_cor, T_corridor, linewidth=2.0, label="Original")
            ax.plot(D_cor, T_c_cor, linewidth=2.0, label="EvacuationC")
            ax.plot(D_cor, times, linewidth=2.0, label="EvacuationPy")
            plt.xticks(D_cor)
            plt.xlim([D_cor[0], D_cor[-1]])
        elif 'disbuild' in args.file.name:
            ax.plot(D_dis, T_c_dis, linewidth=2.0, label="EvacuationC")
            ax.plot(D_dis, times, linewidth=2.0, label="EvacuationPy")
            ax.plot(D_dis, T_dis, linewidth=2.0, label="Рис. 3.23 линия 2")
            plt.xticks(D_dis)
            plt.xlim([D_dis[0], D_dis[-1]])
        else:
            ax.plot(D, times, linewidth=2.0, label="EvacuationPy")
            plt.xticks(D)
            plt.xlim([D[0], D[-1]])

        plt.ylim(bottom=0)
        plt.grid(True)

        plt.legend()  # pyright: ignore [reportUnknownMemberType]
        plt.show()  # pyright: ignore [reportUnknownMemberType]
