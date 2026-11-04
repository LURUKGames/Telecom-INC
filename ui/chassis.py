#!/usr/bin/env python3
"""ui/chassis.py - хелперы имён портов по платам equip["boards"]."""


def board_of_port(equip, port_index):
    """Возвращает dict платы, в которую входит port_index. None если нет."""
    for b in equip.get("boards", []):
        start, end = b["port_range"]
        if start <= port_index < end:
            return b
    return None


def port_name(game, equip, port_index):
    """Формат 'board_id/local_num'. У одиночного устройства board_id=1."""
    b = board_of_port(equip, port_index)
    if b is None:
        return str(port_index + 1)
    start, _ = b["port_range"]
    return f"{b['board_id']}/{port_index - start + 1}"


def boards_summary(equip):
    """[(board_id, n_ports), ...] для UI."""
    return [(b["board_id"], b["port_range"][1] - b["port_range"][0])
            for b in equip.get("boards", [])]