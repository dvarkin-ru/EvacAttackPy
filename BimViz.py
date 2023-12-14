import tkinter
from tkinter import filedialog
import json
from BimEvac import Moving, points
from BimIntruder import Intruder
import math

scale = 50


def is_el_on_lvl(el, lvl):
    ''' Принадлежит ли элемент этажу '''
    el_id = el["Id"]
    for e in lvl['BuildElement']:
        if e['Id'] == el_id:
            return True
    return False


def _point_in_polygon(point, zone_points):
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


def visualization(moving, intruder, is_evac=True):
    # находим offset для canvas
    min_x, min_y, max_x, max_y = 0, 0, 0, 0
    for lvl in moving.bim['Level']:
        for el in lvl['BuildElement']:
            for x, y in points(el):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    offset_x, offset_y = -min_x, -min_y

    def crd(x, y):
        ''' Перевод из координат здания в координаты canvas '''
        return (offset_x+x)*scale, (offset_y-y)*scale

    def cntr(el):
        ''' Центр для canvas по координатам здания '''
        xy = [crd(x, y) for x, y in points(el)]
        return sum((x for x, y in xy))/len(xy), sum((y for x, y in xy))/len(xy)

    i_room = intruder.bim_curr_path[-1]["Id"]
    intruder.victims = moving.zones[i_room]["NumPeople"]
    moving.zones[i_room]["NumPeople"] = 0
    moving.zones[i_room]["Density"] = 0
    moving.zones[i_room]["IsBlocked"] = True

    def vis_step():
        nonlocal i_room, is_evac
        if is_evac:
            moving.step()
        else:
            moving.time += moving.MODELLING_STEP
        if intruder.path_len()/intruder.speed < moving.time:
            intruder.step_next()
            moving.zones[i_room]["IsBlocked"] = False
            i_room = intruder.bim_curr_path[-1]["Id"]
            moving.zones[i_room]["IsBlocked"] = True
            intruder.victims += moving.zones[i_room]["NumPeople"]
            moving.zones[i_room]["NumPeople"] = 0
            moving.zones[i_room]["Density"] = 0
            intr_line(intruder.bim_curr_path[-2], intruder.bim_curr_path[-1])
            intr_lbl.config(text="Ущерб: "+str(int(intruder.victims)))

        time_lbl.config(text="Визуализация идёт {:6.2f} секунд".format(moving.time*60))
        for lvl, c in cs:
            texts = text_id[lvl[moving.lvlname]]
            arrows = arrow_id[lvl[moving.lvlname]]
            for el in lvl['BuildElement']:
                e = el["Id"]
                if e in moving.transits:
                    c.itemconfigure(texts[e], text="{:6.2f}".format(abs(moving.transits[e]["NumPeople"])))
                    if abs(moving.transits[e]["NumPeople"]) < 0.0001:
                        c.itemconfigure(arrows[e], arrow=tkinter.NONE)
                    elif moving.transits[e]["NumPeople"] > 0:
                        c.itemconfigure(arrows[e], arrow=tkinter.LAST)
                    elif moving.transits[e]["NumPeople"] < 0:
                        c.itemconfigure(arrows[e], arrow=tkinter.FIRST)
                if e in moving.zones:
                    c.itemconfigure(texts[e], text="{:6.2f}".format(moving.zones[e]["NumPeople"]))
        nop = sum([x["NumPeople"] for x in moving.zones.values() if x["IsVisited"]])
        if intruder.precalculate_path and not intruder.p_path:
            tkinter.messagebox.showinfo("Визуализация окончена", f"Ущерб {int(intruder.victims)} чел.")
            root.destroy()
        elif is_evac and nop <= 0:
            nop_sz = sum(z["NumPeople"] for z in m.safety_zones)
            tkinter.messagebox.showinfo("Визуализация окончена", f"Ущерб: {int(intruder.victims)} чел. Длительность эвакуации: {moving.time*60:.{5}} с. ({moving.time:.{5}} мин.)")
            root.destroy()

    root = tkinter.Tk()
    root.title("Визуализация")
    tkinter.Button(text="Шаг", command=vis_step).pack()
    time_lbl = tkinter.Label(root, justify=tkinter.CENTER, text='Визуализация не начата')
    time_lbl.pack()
    intr_lbl = tkinter.Label(text="Ущерб: "+str(int(intruder.victims)))
    intr_lbl.pack()
    # Tkinter окно для каждого этажа
    cs = []  # пары этаж-canvas
    for lvl in moving.bim["Level"]:
        top = tkinter.Toplevel()
        top.title(lvl[moving.lvlname])
        frame = tkinter.Frame(top)
        frame.pack(expand=True, fill=tkinter.BOTH)
        c = tkinter.Canvas(frame, scrollregion=(*crd(min_x, max_y), *crd(max_x, min_y)))
        v = tkinter.Scrollbar(frame, orient='vertical')
        v.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        v.config(command=c.yview)
        h = tkinter.Scrollbar(frame, orient='horizontal')
        h.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        h.config(command=c.xview)
        c.config(xscrollcommand=h.set, yscrollcommand=v.set)
        c.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)
        top.attributes("-zoomed", True)
        cs.append((lvl, c))

    def intr_line(fr_room, to_room):
        for lvl, c in cs:
            for el in lvl['BuildElement']:
                if is_el_on_lvl(fr_room, lvl) or is_el_on_lvl(to_room, lvl):
                    c.create_line(cntr(fr_room), cntr(to_room), arrow=tkinter.LAST, fill='red')

    intr_line(intruder.bim_curr_path[-2], intruder.bim_curr_path[-1])

    text_id = dict()  # id текстовых объектов на каждом canvas
    arrow_id = dict()
    # Рисуем фон
    colors = {"Room": "", "DoorWayInt": "yellow", "DoorWayOut": "brown", "DoorWay": "", "Staircase": "green"}
    for lvl, c in cs:
        texts = dict()
        arrows = dict()
        text_id[lvl[moving.lvlname]] = texts
        arrow_id[lvl[moving.lvlname]] = arrows
        for el in lvl['BuildElement']:
            c.create_polygon([crd(x,y) for x, y in points(el)], fill=colors[el['Sign']], outline='black')
            # c.tag_bind(p, "<Button-1>", lambda e, el_id=el['Id']: onclick(el_id))
            num_p = 0
            if el.get('NumPeople'):
                num_p = el.get('NumPeople')
            texts[el["Id"]] = c.create_text(cntr(el), text="{:6.2f}".format(num_p))
            if 'Door' in el["Sign"]:
                zps = points(m.zones[m.transits[el["Id"]]["Output"][0]])
                ps = points(el)
                for p1, p2 in zip(ps, ps[1:]+ps[:1]):
                    if _point_in_polygon(p1, zps) and not _point_in_polygon(p2, zps):
                        arrows[el["Id"]] = c.create_line(crd(*p1), crd(*p2), arrow=tkinter.NONE)
                        break
                if 'DoorWayOut' in el["Sign"]:
                    c.itemconfigure(texts[el["Id"]], text=out_doors.index(el))
##        for i, path in enumerate(paths): 
##            for path_from, path_to in zip(path, path[1:]):
##                if is_el_on_lvl(path_from, lvl) or is_el_on_lvl(path_to, lvl):
##                    c.create_line(cntr(path_from), cntr(path_to), arrow=tkinter.LAST, fill=path_colors[i])
##            if is_el_on_lvl(path[-1], lvl):
##                c.create_text([i+12 for i in cntr(path[-1])], text="BREAK") # окончание пути, смещённое на 12 точек

    root.mainloop()

filename = tkinter.filedialog.askopenfilename(filetypes=(("BIM JSON", "*.json"),))
if not filename:
    exit()
with open(filename) as f:
    j = json.load(f)
    
m = Moving(j)
dens = tkinter.simpledialog.askfloat("Плотность", "Задайте плотность, чел/м2", initialvalue=0.5, minvalue=0.0, maxvalue=1.0)
if dens is None:
    exit()
m.set_density(dens)
m.set_people_by_density()

out_doors = [el for lvl in j['Level'] for el in lvl['BuildElement'] if el['Sign'] == "DoorWayOut"]
door = tkinter.simpledialog.askinteger("Дверь нарушителя", "Задайте номер двери, через которую войдёт нарушитель (пронумерованы при запуске)", initialvalue=0, minvalue=0, maxvalue=len(out_doors))
if door is None:
    exit()
i = Intruder(j, door, precalculate_path=True)
i.speed = tkinter.simpledialog.askinteger("Скорость нарушителя", "Задайте скорость нарушителя, м/мин", initialvalue=60, minvalue=1, maxvalue=200)
if i.speed is None:
    exit()
evac = tkinter.simpledialog.askinteger("Режим", "Задайте режим (0-без эвакуации, 1-с ней)", initialvalue=1, minvalue=0, maxvalue=1)
if evac is None:
    exit()
visualization(m, i, is_evac=bool(evac))
