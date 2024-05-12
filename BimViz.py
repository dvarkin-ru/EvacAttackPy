import tkinter
from tkinter import filedialog
import json
from EvacAttackShared import points, is_el_on_lvl, point_in_polygon
from EvacAttackModel import EvacAttackModel
from pprint import pformat

scale = 18

def visualization():
    # находим offset для canvas
    min_x, min_y, max_x, max_y = 0, 0, 0, 0
    for lvl in j['Level']:
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

    def vis_step():
        moving, intruder = model.moving, model.intruder
        lastroom = intruder.bim_curr_path[-1] if intruder else None
        model.step()
        if intruder and intruder.bim_curr_path[-1] != lastroom:
            intr_line(intruder.bim_curr_path[-2], intruder.bim_curr_path[-1])
            intr_lbl.config(text="Ущерб: "+str(int(intruder.victims)))

        time_lbl.config(text="Визуализация идёт {:6.2f} секунд".format(moving.time*60))
        for lvl, c in cs:
            for el in lvl['BuildElement']:
                e = el["Id"]
                cv_els = el_id_to_cv.get(e)
                if cv_els is None:
                    continue
                if e in moving.transits:
                    c.itemconfigure(cv_els["text"], text="{:6.2f}".format(abs(moving.transits[e]["NumPeople"])))
                    if cv_els.get("arrow") is not None:
                        if abs(moving.transits[e]["NumPeople"]) < 0.0001:
                            c.itemconfigure(cv_els["arrow"], arrow=tkinter.NONE, fill=moving.transits[e].get("Color"),
                                arrowshape=(16, 20, 6))
                        elif moving.transits[e]["NumPeople"] > 0:
                            c.itemconfigure(cv_els["arrow"], arrow=tkinter.LAST, fill=moving.transits[e].get("Color"),
                                arrowshape=(16, 20, 6))
                        elif moving.transits[e]["NumPeople"] < 0:
                            c.itemconfigure(cv_els["arrow"], arrow=tkinter.FIRST, fill=moving.transits[e].get("Color"),
                                arrowshape=(16, 20, 6))
                if e in moving.zones:
                    c.itemconfigure(cv_els["text"], text="{:6.2f}".format(moving.zones[e]["NumPeople"]))
                    c.itemconfigure(cv_els["polygon"], fill=moving.zones[e].get("Color"))
        nop = sum([x["NumPeople"] for x in moving.zones.values() if x["IsVisited"]])
        if intruder and intruder.precalculate_path and intruder.p_path:
            return
        elif moving.active and nop > 0:
            return
        nop_sz = sum(z["NumPeople"] for z in moving.safety_zones)
        tkinter.messagebox.showinfo("Визуализация окончена", f"Ущерб: {int(intruder.victims if intruder else 0)} чел. Длительность визуализации: {moving.time*60:.{5}} с. ({moving.time:.{5}} мин.)"
                                    f" В безопасной зоне {int(nop_sz)} человек")
        root.destroy()

    root = tkinter.Tk()
    root.title("Визуализация")
    tkinter.Button(text="Шаг", command=vis_step).pack()
    time_lbl = tkinter.Label(root, justify=tkinter.CENTER, text='Визуализация не начата')
    time_lbl.pack()
    intr_lbl = tkinter.Label(text="Ущерб: "+str(int(model.intruder.victims if model.intruder else -1)))
    intr_lbl.pack()
    # Tkinter окно для каждого этажа
    cs = []  # пары этаж-canvas
    for lvl in j["Level"]:
        top = tkinter.Toplevel()
        top.title(lvl[model.moving.lvlname])
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
        try:
            top.attributes("-zoomed", True)
        except tkinter.TclError:
            top.wm_state("zoomed")
        cs.append((lvl, c))

    def intr_line(fr_room, to_room):
        for lvl, c in cs:
            for el in lvl['BuildElement']:
                if is_el_on_lvl(fr_room, lvl) or is_el_on_lvl(to_room, lvl):
                    c.create_line(cntr(fr_room), cntr(to_room), arrow=tkinter.LAST, fill='red')
    if model.intruder:
        intr_line(model.intruder.bim_curr_path[-2], model.intruder.bim_curr_path[-1])

    el_id_to_cv = dict()  # id текстовых объектов на каждом canvas
    # Рисуем фон
    colors = {"Room": "", "DoorWayInt": "yellow", "DoorWayOut": "brown", "DoorWay": "", "Staircase": "green"}
    for lvl, c in cs:
        for el in lvl['BuildElement']:
            p = c.create_polygon([crd(x, y) for x, y in points(el)], fill=colors[el['Sign']], outline='black')
            c.tag_bind(p, "<Button-1>", lambda e, el=el: tkinter.messagebox.showinfo("Инфо об объекте", pformat(el, compact=True, depth=2)))
            num_p = 0
            if el.get('NumPeople'):
                num_p = el.get('NumPeople')
            t = c.create_text(cntr(el), text="{:6.2f}".format(num_p))
            el_id_to_cv[el["Id"]] = {"polygon": p, "text": t}
            if 'Door' in el["Sign"]:
                zps = points(model.moving.zones[model.moving.transits[el["Id"]]["Output"][0]])
                ps = points(el)
                for p1, p2 in zip(ps, ps[1:]+ps[:1]):
                    if point_in_polygon(p1, zps) and not point_in_polygon(p2, zps):
                        el_id_to_cv[el["Id"]]["arrow"] = c.create_line(crd(*p1), crd(*p2), arrow=tkinter.NONE)
                        break
                if 'DoorWayOut' in el["Sign"]:
                    c.itemconfigure(t, text=out_doors.index(el))
    root.mainloop()


filename = filedialog.askopenfilename(filetypes=(("BIM JSON", "*.json"),))
if not filename:
    exit()
with open(filename) as f:
    j = json.load(f)


model = EvacAttackModel(j)
dens = tkinter.simpledialog.askfloat("Плотность", "Задайте плотность, чел/м2", initialvalue=0.5, minvalue=0.0, maxvalue=1.0)
if dens is None:
    exit()
model.moving.set_density(dens)
model.moving.set_people_by_density()

# Распределяем цвета
##fancy_colors = ["gold", "silver", "cobalt", "brick", "banana", "orange", "carrot", "olive", "melon", "plum", "chocolate",
##                "peacock", "raspberry", "tomato1", "mint", "forestgreen", "coral", "orchid"] # not working
##fancy_colors = ["chocolate", "LemonChiffon4", "PeachPuff4", "olive", "tomato4", "forest green", "peru", "coral4",
##                "orchid4", "bisque4", "seashell4", "old lace", "wheat", "gold", "silver", "orange", "plum", "lime",  "lavender"]
fancy_colors = ["cyan", "magenta", "chocolate", "green", "blue"] * 10
for col, zone in zip(fancy_colors, model.moving.safety_zones):
    zone["Color"] = col

out_doors = [el for lvl in j['Level'] for el in lvl['BuildElement'] if el['Sign'] == "DoorWayOut"]
door = tkinter.simpledialog.askinteger("Дверь нарушителя", "Задайте номер двери, через которую войдёт нарушитель (номера будут показаны в начале визуализации)",
                                       initialvalue=0, minvalue=0, maxvalue=len(out_doors))
prec = tkinter.messagebox.askyesno("Режим нарушителя", "Расчитать путь нарушителя при старте, чтобы движение людей не влияло на путь?")
i_type = tkinter.simpledialog.askinteger("Тип нарушителя", "Задайте тип нарушителя, 1 для простого нарушителя", initialvalue=1, minvalue=1, maxvalue=3)
i_speed = tkinter.simpledialog.askinteger("Скорость нарушителя", "Задайте скорость нарушителя, м/мин", initialvalue=60, minvalue=1, maxvalue=200)
if None not in (door, i_type, i_speed):
    model.set_intruder(door, prec, i_type, i_speed)
model.moving.active = tkinter.messagebox.askyesno("Режим эвакуации", "Эвакуировать людей? Если нет, то люди не будут двигаться.")
visualization()
