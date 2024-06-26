import math
from operator import itemgetter, truediv
from EvacAttackShared import cntr_real, dict_peak


class Intruder:

    def get_door(self, room1, room2):
        if room1 == room2:
            print("Get_door: same room as arguments! "+room1["Name"])
            return
        for door1 in room1["Output"]:
            for door2 in room2["Output"]:
                if door1 == door2:
                    return self.get_el(door1)

    def neighbours(self, start_room):
        ''' Находит соседние через DoorWayInt комнаты у данной комнаты, возвращает generator :) '''
        return (self.get_el(room_id) for door_id in start_room["Output"] if self.get_el(door_id)['Sign'] in ('DoorWayInt', 'DoorWay') for room_id in self.get_el(door_id)["Output"] if room_id != start_room["Id"])

    def bfs(self, v, Q, visits):
        ''' Проходимся по графу по ширине '''
        if not (visits.get(v["Id"]) is None):
            return
        visits[v['Id']] = 0
        for i in self.neighbours(v):  # Все смежные с v вершины
            if visits.get(i['Id']) is None:
                Q.append(i)
                i["GLevel"] = v["GLevel"] + 1
        while Q:
            self.bfs(Q.pop(0), Q, visits)

    def get_el(self, el_id):
        ''' Находит элемент по Id '''
        return self.bim_el.get(el_id)
        # for lvl in self.j['Level']:
        #     for e in lvl['BuildElement']:
        #         if e['Id'] == el_id:
        #             return e

    def step(self, from_room, to_room, vis, curr_path):
        ''' Рекурсивная функция '''
        door = from_room if from_room["Sign"] == 'DoorWayOut' else self.get_door(from_room, to_room)  # для входа
        vis[door["Id"]] += 1
        vis[to_room["Id"]] += 1
        eff = to_room['NumPeople']
        variants = [self.step(to_room, next_to_room, vis.copy(), curr_path + [to_room]) for next_to_room in self.step_variants(to_room, vis.copy(), curr_path + [to_room])]
        # Условия прекращения рекурсии
        if not variants or vis[door["Id"]] >= 3 or to_room["GLevel"] == self.max_lvl:
            return curr_path + [to_room], eff
        # Выбираем самый эффективный вариант
        path, max_eff = max(variants, key=itemgetter(1))
        return path, max_eff + eff

    def vision(self, room, vis, curr_path, lvl=0):
        curr_room_dist = math.dist(cntr_real(curr_path[-1]), cntr_real(curr_path[-2]))
        if lvl >= self.vision_lvl:
            return room["NumPeople"], curr_room_dist
        vis[room["Id"]] += 1
        v = [self.vision(n, vis.copy(), curr_path + [n], lvl + 1) for n in self.neighbours(room) if vis[n["Id"]] == 0]
        pep, dist = sum((p for p, d in v)), sum((d for p, d in v))
        return pep + room["NumPeople"], dist + curr_room_dist

    def step_variants(self, room, vis, curr_path):
        if self.intruder_type == 1:
            return [n for n in self.neighbours(room) if n["GLevel"] == room["GLevel"] + 1 and n not in self.disabled_rooms]
        elif self.intruder_type in (2, 3):
            # Варианты перехода во все непосещённые помещения
            v = [n for n in self.neighbours(room) if vis[n["Id"]] == 0 and n not in self.disabled_rooms]
            if self.intruder_type == 3:
                # Нарушитель типа 3 предпочтёт путь с наибольшим уроном за время
                visible = [(truediv(*self.vision(n, vis.copy(), curr_path + [n])), n) for n in v]
            else:
                # Нарушитель типа 2 предпочтёт путь с наибольшим уроном в принципе
                visible = [(self.vision(n, vis.copy(), curr_path + [n])[0], n) for n in v]
            if visible:  # если такие находятся
                max_eff = max(visible, key=itemgetter(0))
                if max_eff[0] > 0:  # если хотя бы на одном из них есть люди
                    return [max_eff[1]]
                else:
                    # выбираем высокоуровневые варианты
                    hi_lev = dict_peak(v, "GLevel", True)  # [max(v, key=itemgetter("GLevel"))]
                    # из них можно выбрать вариант с наиболее быстро преодолеваемыми дверными проёмами
                    # а пока выберем вариант с наибольшим возможным расстоянием (наименьшее кол-во дверей за расстояние)
                    return [max(((self.vision(n, vis.copy(), curr_path + [n])[1], n) for n in hi_lev), key=itemgetter(0))[1]]

            # если непосещённых нет, идём назад, но не назад в назад
            for back in reversed(curr_path):
                if room == back:
                    continue
                door = self.get_door(room, back)
                if door and vis[door["Id"]] <= 1:
                    return [back]
            return []  # ???

    def __init__(self, j, choosen_door, precalculate_path=False, intruder_type=1, intruder_speed=60, disabled_rooms=[]):
        self.intruder_type = intruder_type
        self.vision_lvl = 3
        self.j = j
        self.bim_el = {e['Id']: e for lvl in self.j['Level'] for e in lvl['BuildElement']}
        self.disabled_rooms = disabled_rooms
        top_door = self.get_out_doors()[choosen_door]
        top_room = self.get_el(top_door['Output'][0])
        top_room["GLevel"] = 0
        self.bfs(top_room, [], {})
        self.max_lvl = max((e["GLevel"] for lvl in self.j['Level'] for e in lvl['BuildElement'] if e.get("GLevel")))
        self.bim_visits = {e['Id']: 0 for lvl in self.j['Level'] for e in lvl['BuildElement']}
        self.bim_curr_path = [top_door, top_room]
        self.bim_visits[top_door["Id"]] += 1
        self.bim_visits[top_room["Id"]] += 1
        self.speed = intruder_speed
        self.precalculate_path = precalculate_path
        if precalculate_path:
            self.p_path = self.step(self.get_el(top_door["Id"]), top_room, self.bim_visits.copy(), [])[0][1:]

    def step_next(self):
        if self.precalculate_path:
            nextp = self.p_path.pop(0) if self.p_path else None
        elif self.intruder_type==1:
            # Повторяем последний шаг и берём путь дальше
            nextp, next_eff = self.step(*self.bim_curr_path[-2:], self.bim_visits.copy(), self.bim_curr_path.copy())
            if len(nextp) > len(self.bim_curr_path)+1:
                nextp = nextp[len(self.bim_curr_path)+1]
            else:
                nextp = None
        else:
            nextp = self.step_variants(self.bim_curr_path[-1], self.bim_visits, self.bim_curr_path)[0]
        if nextp:
            self.bim_visits[nextp["Id"]] += 1
            self.bim_visits[self.get_door(self.bim_curr_path[-1], nextp)["Id"]] += 1
            self.bim_curr_path.append(nextp)
        else:
            pass # print("INTRUDER NO PATH")

    def path_len(self):
        len_path = 0
        for a, b in zip(self.bim_curr_path, self.bim_curr_path[1:]):
            len_path += math.dist(cntr_real(a), cntr_real(b))
        return len_path

    def get_out_doors(self):
        ''' Ищем входные двери'''
        return [el for lvl in self.j['Level'] for el in lvl['BuildElement'] if el['Sign'] == "DoorWayOut"]
