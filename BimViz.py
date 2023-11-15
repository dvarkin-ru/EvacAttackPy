import tkinter
from tkinter.messagebox import showerror, showwarning, showinfo
import argparse
import json
from BimEvac import Moving, points
import math

scale = 50

def visualization(moving):
    # находим offset для canvas
    text_id = dict()
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
        return (x+offset_x)*scale, (y+offset_y)*scale

    def cntr(el):
        ''' Центр для canvas по координатам здания '''
        xy = [crd(x, y) for x, y in points(el)]
        return sum((x for x, y in xy))/len(xy), sum((y for x, y in xy))/len(xy)

    def vis_step():
        moving.step()
        time_lbl.config(text="Визуализация идёт {:6.2f} секунд".format(moving.time*60))
        for lvl, c in cs:
            texts = text_id[lvl[moving.lvlname]]
            for el in lvl['BuildElement']:
                e = el["Id"]
                if e in moving.transits:
                    c.itemconfigure(texts[e], text="{:6.2f}".format(moving.transits[e]["NumPeople"]))
                if e in moving.zones:
                    c.itemconfigure(texts[e], text="{:6.2f}".format(moving.zones[e]["NumPeople"]))
        nop = sum([x["NumPeople"] for x in moving.zones.values() if x["IsVisited"]])
        if nop <= 0:
            nop_sz = sum(z["NumPeople"] for z in m.safety_zones)
            showinfo("Визуализация окончена", f"Количество человек: {nop_sz:.{5}} Длительность эвакуации: {moving.time*60:.{5}} с. ({moving.time:.{5}} мин.)")
            root.destroy()

    root = tkinter.Tk()
    root.title("Визуализация")
    tkinter.Button(text="Шаг", command=vis_step).pack()
    time_lbl = tkinter.Label(root, justify=tkinter.CENTER, text='Визуализация не начата')
    time_lbl.pack()
    # Tkinter окно для каждого этажа
    cs = []
    for lvl in moving.bim["Level"]:
        top = tkinter.Toplevel()
        top.title(lvl[moving.lvlname])
        frame=tkinter.Frame(top)
        frame.pack(expand=True, fill=tkinter.BOTH)
        c = tkinter.Canvas(frame, scrollregion=(*crd(min_x, min_y), *crd(max_x, max_y)))
        v = tkinter.Scrollbar(frame, orient = 'vertical')
        v.pack(side=tkinter.RIGHT, fill = tkinter.Y)
        v.config(command=c.yview)
        h = tkinter.Scrollbar(frame, orient = 'horizontal')
        h.pack(side=tkinter.BOTTOM, fill = tkinter.X)
        h.config(command=c.xview)
        c.config(xscrollcommand=h.set, yscrollcommand=v.set)
        c.pack(side=tkinter.LEFT,expand=True,fill=tkinter.BOTH)
        cs.append((lvl, c))

    # Рисуем фон
    colors = {"Room": "", "DoorWayInt": "yellow", "DoorWayOut": "brown", "DoorWay": "", "Staircase": "green"}
    path_colors = ("red", "green", "blue")
    for lvl, c in cs:
        texts = dict()
        text_id[lvl[moving.lvlname]] = texts
        for el in lvl['BuildElement']:
            p = c.create_polygon([crd(x,y) for x, y in points(el)], fill=colors[el['Sign']], outline='black')
##            c.tag_bind(p, "<Button-1>", lambda e, el_id=el['Id']: onclick(el_id))
            t = c.create_text(cntr(el), text="{:6.2f}".format(el['NumPeople']))
            texts[el["Id"]] = t
            if 'Door' in el["Sign"]:
                # TODO: стрелочка по стороне проёма
                c_door = crd(*points(el)[0])
                c_up = cntr(m.zones[m.transits[el["Id"]]["Output"][0]])
                v = (c_door[0]-c_up[0], c_door[1]-c_up[1])
                unit_vector = (v[0]/math.dist(c_door, c_up), v[1]/math.dist(c_door, c_up))
                c_up = (c_door[0]-unit_vector[0]*scale, c_door[1]-unit_vector[1]*scale)
                c.create_line(c_door, c_up, arrow=tkinter.FIRST)
##        for i, path in enumerate(paths): 
##            for path_from, path_to in zip(path, path[1:]):
##                if is_el_on_lvl(path_from, lvl) or is_el_on_lvl(path_to, lvl):
##                    c.create_line(cntr(path_from), cntr(path_to), arrow=tkinter.LAST, fill=path_colors[i])
##            if is_el_on_lvl(path[-1], lvl):
##                c.create_text([i+12 for i in cntr(path[-1])], text="BREAK") # окончание пути, смещённое на 12 точек


    root.mainloop()


parser = argparse.ArgumentParser(description='Bim modeling of evacuation when attack')
parser.add_argument('file', type=argparse.FileType('r')) # file already opened by argparse
args = parser.parse_args()

m = Moving(json.load(args.file))

m.set_density(1.0)
m.set_people_by_density()

visualization(m)


