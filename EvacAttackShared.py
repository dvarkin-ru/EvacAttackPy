import math
from operator import itemgetter

def points(el):
    if "points" in el["XY"][0]:
        return [(xy["x"], xy["y"]) for xy in el["XY"][0]["points"]]
    else:
        return el["XY"][0][:-1]

def cntr_real(el):
    ''' Центр в координатах здания '''
    xy = points(el)
    return sum((x for x, y in xy)) / len(xy), sum((y for x, y in xy)) / len(xy)

def room_area(el):
    # print(xy)
    xy = points(el)
    return math.fabs(0.5*sum((x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(xy, xy[1:]+xy[:1]))))

def is_el_on_lvl(el, lvl):
    ''' Принадлежит ли элемент этажу '''
    el_id = el["Id"]
    for e in lvl['BuildElement']:
        if e['Id'] == el_id:
            return True
    return False

def point_in_polygon(point, zone_points):
    """
    Проверка вхождения точки в прямоугольник
    """
    c = False
    for p1, p2 in zip(zone_points, zone_points[1:]+zone_points[:1]):
        if math.dist(p1, point) + math.dist(point, p2) == math.dist(p1, p2):
            return True
        if (((p1[1] > point[1]) != (p2[1] > point[1])) and (point[0] < (p2[0]-p1[0]) * (point[1]-p1[1]) / (p2[1]-p1[1]) + p1[0])):
            c = not c
    return c

def dict_peak(d, key, reverse):
    ''' Возвращает крайние элементы словаря d по ключу key,
    это минимальные элементы если reverse == False, иначе максимальные '''
    d = sorted(d, key=itemgetter(key), reverse=reverse)
    return [i for i in d if i[key] == d[0][key]]
