#!/usr/bin/env python3
"""ui/net_helpers.py - логика портов/LACP/скоростей (чистые функции над game/equip)."""

from config import (
    COLOR_STATUS_UP, COLOR_STATUS_DOWN, COLOR_STATUS_ERROR, COLOR_STATUS_LACP,
    COLOR_PORT_DOWN, COLOR_PORT_DOWN_HI, COLOR_PORT_UP, COLOR_PORT_UP_HI,
    COLOR_PORT_ERROR, COLOR_PORT_ERROR_HI, COLOR_PORT_MISMATCH, COLOR_PORT_LACP,
    COLOR_TARIFF,
)


def find_cable_for_port(game, equip_id, port_index):
    if game is None:
        return None
    for cable in game.cables:
        if cable["a"] == equip_id and cable["port_a"] == port_index:
            return cable
        if cable.get("b") == equip_id and cable.get("port_b") == port_index:
            return cable
    return None


def port_in_lacp(equip, port_index):
    for grp in equip.get("lacp_groups", []):
        if port_index in grp["ports"]:
            return grp
    return None


def _notify_speed_changed(game):
    if game is not None and hasattr(game, "recompute_mismatch"):
        game.recompute_mismatch()


def toggle_port_speed(game, equip, port_index):
    port = equip["ports"][port_index]
    if port_in_lacp(equip, port_index) is not None:
        print("Порт в составе LACP — настройка скорости через логический порт")
        return
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable["type"] == "cable_100":
            print("Кабель 100Мб ограничивает скорость")
            return
        port["speed"] = 100 if port["speed"] == 1000 else 1000
        _notify_speed_changed(game)
        return
    port["speed"] = 100 if port["speed"] == 1000 else 1000
    _notify_speed_changed(game)


def toggle_lacp_speed(grp, game=None):
    grp["speed"] = 100 if grp.get("speed", 1000) == 1000 else 1000
    _notify_speed_changed(game)


def equip_type_label(equip):
    t = equip["type"]
    if t == "router":
        return "Роутер"
    n = len(equip["ports"])
    return f"Свитч {n}p"


def port_status_text_color(game, equip, port_index):
    port = equip["ports"][port_index]
    grp = port_in_lacp(equip, port_index)
    if port["free"]:
        if grp is not None:
            return f"В составе {grp['name']}", COLOR_STATUS_LACP
        return "Down", COLOR_STATUS_DOWN
    # Порт физически используется — статус отражает кабель,
    # даже если он входит в LACP (физика важнее для диагностики).
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable.get("speed_mismatch"):
            return "Speed Mismatch", COLOR_PORT_MISMATCH
        if not cable.get("signal_ok", True):
            return "ОШИБКА >150м", COLOR_STATUS_ERROR
    conn = port["connection"]
    if conn:
        if conn.get("to_dc"):
            tar = conn.get("tariff", "ЦОД")
            return f"Магистраль [{tar}]", COLOR_TARIFF
        suffix = f" ({grp['name']})" if grp is not None else ""
        return f"Up #{conn['to_id']}:{conn['to_port'] + 1}{suffix}", COLOR_STATUS_UP
    return "Up", COLOR_STATUS_UP


def port_fill_color(game, equip, port_index, hover=False):
    port = equip["ports"][port_index]
    if port["free"]:
        if port_in_lacp(equip, port_index) is not None:
            return COLOR_PORT_LACP
        return COLOR_PORT_DOWN_HI if hover else COLOR_PORT_DOWN
    cable = find_cable_for_port(game, equip["id"], port_index)
    if cable is not None:
        if cable.get("speed_mismatch"):
            return COLOR_PORT_MISMATCH
        if not cable.get("signal_ok", True):
            return COLOR_PORT_ERROR_HI if hover else COLOR_PORT_ERROR
    return COLOR_PORT_UP_HI if hover else COLOR_PORT_UP


def lacp_effective_label(equip, port_index):
    grp = port_in_lacp(equip, port_index)
    if grp is not None:
        return grp["name"]
    return equip["ports"][port_index].get("label", "")

