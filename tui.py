#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#

"""
Terminal UI for the VPC IP Fragmentation Viewer.

A disk-defrag style, keyboard-driven view of AWS VPC IP allocation built on
Textual. It reuses the same AWS querying + fragmentation logic as the Flask API
(see vpc_data.py).

Run with:
    python tui.py
    # or, once installed as part of requirements.txt:
    textual run tui.py

Requires AWS credentials in the environment (same as the web app) and the
ec2:Describe* / ec2:GetSubnetCidrReservations permissions.
"""

import asyncio

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Select,
    Static,
)

import vpc_data


# Status -> hex color, mirroring the React IpVisualization palette.
STATUS_COLORS = {
    "used_primary": "#3b82f6",       # blue
    "used_secondary": "#06b6d4",     # cyan
    "used_prefix_delegation": "#8b5cf6",  # purple
    "reserved": "#64748b",           # slate (AWS reserved)
    "cidr_reservation_explicit": "#f59e0b",  # amber
    "cidr_reservation_prefix": "#f97316",    # orange
    "free": "#e2e8f0",               # light (free/available), like a defrag map
}

# Bright cursor color, distinct from every palette entry.
CURSOR_COLOR = "#f472b6"  # pink

# The legend shown on the Cluster Map header: (label, color).
LEGEND = [
    ("Primary", STATUS_COLORS["used_primary"]),
    ("Secondary", STATUS_COLORS["used_secondary"]),
    ("Prefix", STATUS_COLORS["used_prefix_delegation"]),
    ("CIDR-Resv", STATUS_COLORS["cidr_reservation_explicit"]),
    ("AWS-Resv", STATUS_COLORS["reserved"]),
    ("Free", STATUS_COLORS["free"]),
]


def build_legend():
    """A one-line legend of colored swatches, defrag-tool style."""
    t = Text()
    for label, color in LEGEND:
        t.append("  ", style=f"on {color}")
        t.append(f" {label} ")
    t.append("  ", style=f"on {CURSOR_COLOR}")
    t.append(" Cursor")
    return t


def ip_color(ip):
    """Return the hex color for an IP-map entry."""
    status = ip["status"]
    details = ip.get("details") or {}
    if status == "used":
        t = details.get("type")
        if t == "secondary":
            return STATUS_COLORS["used_secondary"]
        if t == "prefix_delegation":
            return STATUS_COLORS["used_prefix_delegation"]
        return STATUS_COLORS["used_primary"]
    if status == "reserved":
        return STATUS_COLORS["reserved"]
    if status == "cidr_reservation":
        if details.get("type") == "prefix":
            return STATUS_COLORS["cidr_reservation_prefix"]
        return STATUS_COLORS["cidr_reservation_explicit"]
    return STATUS_COLORS["free"]


class IpGrid(Static):
    """A navigable disk-defrag style grid of IP blocks.

    Arrow keys / hjkl move a cursor over the blocks; each move posts an
    ``IpSelected`` message so a details panel can update (the TUI equivalent of
    the web hover tooltip).
    """

    # Each cell is CELL_W chars wide with the gridlines baked into the glyphs
    # (no separate gap column), so a row of N cells is exactly N*CELL_W chars.
    # COLS is recomputed from the widget's width so the grid always fills the
    # map panel horizontally.
    CELL_W = 2
    COLS = 32
    can_focus = True

    class Selected(Message):
        """Posted when the grid cursor moves onto an IP entry."""

        def __init__(self, ip):
            self.ip = ip
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ips = []
        self.cursor = 0
        self.COLS = type(self).COLS  # instance copy, resized to fit width

    def set_ips(self, ips):
        self._ips = ips or []
        self.cursor = 0
        self._fit_cols()
        self.refresh_grid()
        self._emit_selection()

    def _fit_cols(self):
        """Choose the largest column count whose row fits the current width."""
        width = self.size.width
        if width <= 0:
            return False
        cols = max(1, width // self.CELL_W)  # gridlines are baked into the cells
        if cols != self.COLS:
            self.COLS = cols
            return True
        return False

    def on_resize(self, event):
        # Reflow to fill the newly available width.
        if self._fit_cols():
            self.refresh_grid()

    def refresh_grid(self):
        self.update(self._render_grid())

    def _render_grid(self):
        if not self._ips:
            return Text("Select a subnet to load its IP cluster map.", style="dim italic")

        # Each IP is a 2-wide cell with both gridlines baked into the glyphs so
        # the horizontal and vertical gaps are the same thin 1/8 of a character:
        #   "▇" (lower seven-eighths) leaves a 1/8 dark sliver at the TOP    -> horizontal gridline
        #   "▉" (left  seven-eighths) leaves a 1/8 dark sliver at the RIGHT  -> vertical gridline
        # The two glyphs share the cell's color so it reads as one block, and
        # cells sit flush against each other (no wasted blank column/row). The
        # cursor is a solid "██" block so it stands out.
        cell = "▇" * (self.CELL_W - 1) + "▉"
        cursor = "█" * self.CELL_W
        pad = " " * self.CELL_W
        text = Text()
        n = len(self._ips)
        rows = (n + self.COLS - 1) // self.COLS
        for r in range(rows):
            for c in range(self.COLS):
                i = r * self.COLS + c
                if i >= n:
                    text.append(pad)  # pad past the last IP
                    continue
                if i == self.cursor:
                    text.append(cursor, style=CURSOR_COLOR)
                else:
                    text.append(cell, style=ip_color(self._ips[i]))
            if r < rows - 1:
                text.append("\n")
        return text

    def _clamp(self, value):
        if not self._ips:
            return 0
        return max(0, min(value, len(self._ips) - 1))

    def _emit_selection(self):
        if self._ips:
            self.post_message(IpGrid.Selected(self._ips[self.cursor]))

    def on_key(self, event):
        if not self._ips:
            return
        key = event.key
        moved = True
        if key in ("right", "l"):
            self.cursor = self._clamp(self.cursor + 1)
        elif key in ("left", "h"):
            self.cursor = self._clamp(self.cursor - 1)
        elif key in ("down", "j"):
            self.cursor = self._clamp(self.cursor + self.COLS)
        elif key in ("up", "k"):
            self.cursor = self._clamp(self.cursor - self.COLS)
        elif key == "home":
            self.cursor = 0
        elif key == "end":
            self.cursor = len(self._ips) - 1
        else:
            moved = False
        if moved:
            event.stop()
            event.prevent_default()
            self.refresh_grid()
            self._emit_selection()


def frag_level(score):
    """Map a fragmentation score to (label, color)."""
    if score < 20:
        return "Low", "#10b981"
    if score < 50:
        return "Moderate", "#f59e0b"
    return "High", "#ef4444"


class VpcFragTUI(App):
    CSS = """
    Screen {
        background: #071a3f;
        color: #e2e8f0;
    }

    Header {
        background: #1d4ed8;
        color: #ffffff;
    }

    #controls {
        height: auto;
        padding: 0 1;
        background: #0b2a63;
    }

    #controls Select {
        width: 1fr;
    }

    #status {
        height: 1;
        padding: 0 1;
        color: #fbbf24;
        background: #0b2a63;
    }

    #body {
        height: 1fr;
    }

    /* Left: the big IP cluster map. The whole column is one bordered box so
       its top/bottom edges line up with the stacked panels on the right. */
    #left {
        width: 62%;
        border: round #3b82f6;
        padding: 0 1;
    }

    #legend {
        height: 1;
    }

    #grid-scroll {
        height: 1fr;
        background: #071a3f;
        overflow-x: hidden;
    }

    #ip-grid {
        width: 1fr;
        height: auto;
    }

    #ip-details {
        height: 2;
        color: #93c5fd;
    }

    /* Right: statistics on top, subnet list below */
    #right {
        width: 38%;
    }

    #stats {
        height: 45%;
        padding: 0 1;
        border: round #3b82f6;
    }

    #subnet-table {
        height: 1fr;
        border: round #3b82f6;
    }

    #subnet-table > .datatable--cursor {
        background: #14b8a6;
        color: #042f2e;
    }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    TITLE = "☁ VPC IP Fragmentation Viewer"

    def __init__(self):
        super().__init__()
        self._subnets_by_id = {}
        self._selected_subnet = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="controls"):
            yield Select([], prompt="Select region…", id="region-select")
            yield Select([], prompt="Select VPC…", id="vpc-select")
        yield Label("Loading regions…", id="status")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static(build_legend(), id="legend")
                with ScrollableContainer(id="grid-scroll"):
                    yield IpGrid(id="ip-grid")
                yield Static("Move the cursor over the map to inspect an IP.", id="ip-details")
            with Vertical(id="right"):
                yield Static("Select a subnet to view statistics.", id="stats")
                yield DataTable(id="subnet-table", cursor_type="row")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#subnet-table", DataTable)
        table.add_columns("Name", "CIDR", "AZ", "Used", "Avail", "Util%", "Frag")
        # Panel titles, defrag-tool style.
        self.query_one("#left").border_title = "IP Cluster Map"
        self.query_one("#stats", Static).border_title = "Subnet Statistics"
        table.border_title = "Subnets"
        self.load_regions()

    def set_status(self, message):
        self.query_one("#status", Label).update(message)

    # ----- data loading workers -------------------------------------------

    @work(exclusive=False)
    async def load_regions(self):
        self.set_status("Loading regions…")
        try:
            regions = await asyncio.to_thread(vpc_data.list_regions)
        except Exception as e:
            self.set_status(f"Error loading regions: {e}")
            return
        select = self.query_one("#region-select", Select)
        select.set_options([(r["name"], r["id"]) for r in regions])
        default = next((r["id"] for r in regions if r["id"] == vpc_data.DEFAULT_REGION), None)
        if default:
            select.value = default
        else:
            self.set_status("Select a region to begin.")

    @work(exclusive=True)
    async def load_vpcs(self, region):
        self.set_status(f"Loading VPCs in {region}…")
        try:
            vpcs = await asyncio.to_thread(vpc_data.list_vpcs, region)
        except Exception as e:
            self.set_status(f"Error loading VPCs: {e}")
            return
        select = self.query_one("#vpc-select", Select)
        options = [(f"{v['name']} ({v['cidr']})", v["id"]) for v in vpcs]
        select.set_options(options)
        select.value = Select.BLANK
        self.set_status(f"{len(vpcs)} VPC(s) in {region}. Select a VPC.")

    @work(exclusive=True)
    async def load_subnets(self, region, vpc_id):
        self.set_status(f"Loading subnets for {vpc_id}…")
        table = self.query_one("#subnet-table", DataTable)
        table.clear()
        self._subnets_by_id = {}
        try:
            subnets = await asyncio.to_thread(vpc_data.get_vpc_subnets, vpc_id, region)
        except Exception as e:
            self.set_status(f"Error loading subnets: {e}")
            return
        for s in subnets:
            self._subnets_by_id[s["id"]] = s
            label, _ = frag_level(s["fragmentationScore"])
            table.add_row(
                s["name"],
                s["cidr"],
                s["availabilityZone"],
                str(s["usedIps"]),
                str(s["availableIps"]),
                f"{s['utilization']:.1f}",
                f"{s['fragmentationScore']:.0f} {label}",
                key=s["id"],
            )
        self.set_status(f"{len(subnets)} subnet(s). Select one to view its IP map.")

    @work(exclusive=True)
    async def load_ip_map(self, region, subnet_id):
        self.set_status(f"Loading IP map for {subnet_id}…")
        try:
            data = await asyncio.to_thread(vpc_data.get_subnet_ip_map, subnet_id, region)
        except Exception as e:
            self.set_status(f"Error loading IP map: {e}")
            return
        self.query_one("#ip-grid", IpGrid).set_ips(data["ips"])
        self._render_stats(self._subnets_by_id.get(subnet_id), data)
        self.query_one("#grid-scroll").scroll_home(animate=False)
        self.set_status(
            f"{data['totalIps']} IPs — {data['usedIps']} used, "
            f"{data['freeIps']} free, {data['reservedIps']} AWS-reserved, "
            f"{data['cidrReservationIps']} CIDR-reserved."
        )

    # ----- rendering helpers ----------------------------------------------

    def _render_stats(self, subnet, ip_data):
        if not subnet:
            return
        d = subnet.get("fragmentationDetails") or {}
        label, color = frag_level(subnet["fragmentationScore"])

        t = Text()
        t.append(f"{subnet['name']}\n", style="bold")
        t.append(f"{subnet['id']}  •  {subnet['cidr']}  •  {subnet['availabilityZone']}\n\n",
                 style="dim")

        t.append("Allocation   ", style="bold")
        t.append(
            f"total {subnet['totalIps']}   used {subnet['usedIps']}   "
            f"avail {subnet['availableIps']}   reserved {subnet['reservedIps']}   "
            f"util {subnet['utilization']:.1f}%\n"
        )
        t.append("IP types     ", style="bold")
        t.append(
            f"primary {subnet['primaryIps']}   secondary {subnet['secondaryIps']}   "
            f"prefix-deleg {subnet['prefixDelegationIps']}   "
            f"cidr-resv {subnet['cidrReservationIps']}\n"
        )
        t.append("Fragmentation ", style="bold")
        t.append(f"{subnet['fragmentationScore']:.1f} ", style=f"bold {color}")
        t.append(f"({label})\n", style=color)
        t.append(
            f"  gaps {d.get('num_gaps', 0)}   "
            f"largest-free {d.get('largest_gap', 0)}   "
            f"avg-gap {d.get('avg_gap_size', 0)}   "
            f"usable /28 {d.get('usable_prefixes', 0)}\n"
        )
        self.query_one("#stats", Static).update(t)

    def _render_ip_details(self, ip):
        t = Text()
        t.append(f"{ip['ip']}  ", style="bold")
        color = ip_color(ip)
        details = ip.get("details") or {}
        status = ip["status"]

        if status == "used":
            typ = details.get("type", "used")
            t.append(f"[{typ}]", style=color)
            eni = details.get("interfaceId")
            if eni:
                t.append(f"  ENI {eni}", style="dim")
            desc = details.get("description")
            if desc:
                t.append(f"\n  {desc}", style="dim")
            resv = details.get("cidrReservation")
            if resv:
                t.append(
                    f"\n  ↳ in CIDR reservation {resv.get('cidr')} ({resv.get('type')})",
                    style=STATUS_COLORS["cidr_reservation_explicit"],
                )
        elif status == "reserved":
            t.append("[AWS reserved]", style=color)
        elif status == "cidr_reservation":
            t.append(f"[CIDR reservation • {details.get('type')}]", style=color)
            t.append(f"  block {details.get('cidr')}", style="dim")
            if details.get("description"):
                t.append(f"\n  {details['description']}", style="dim")
            if details.get("reservationId"):
                t.append(f"\n  {details['reservationId']}", style="dim")
        else:
            t.append("[free / available]", style=color)

        self.query_one("#ip-details", Static).update(t)

    # ----- event handlers -------------------------------------------------

    @on(Select.Changed, "#region-select")
    def _region_changed(self, event):
        if event.value is Select.BLANK:
            return
        # Reset downstream selections.
        self.query_one("#vpc-select", Select).set_options([])
        self.query_one("#subnet-table", DataTable).clear()
        self.query_one("#ip-grid", IpGrid).set_ips([])
        self.load_vpcs(event.value)

    @on(Select.Changed, "#vpc-select")
    def _vpc_changed(self, event):
        if event.value is Select.BLANK:
            return
        region = self.query_one("#region-select", Select).value
        self.query_one("#ip-grid", IpGrid).set_ips([])
        self.load_subnets(region, event.value)

    @on(DataTable.RowSelected, "#subnet-table")
    def _subnet_selected(self, event):
        subnet_id = event.row_key.value
        if not subnet_id:
            return
        self._selected_subnet = subnet_id
        region = self.query_one("#region-select", Select).value
        self.query_one("#ip-grid", IpGrid).focus()
        self.load_ip_map(region, subnet_id)

    @on(IpGrid.Selected)
    def _ip_hovered(self, event):
        self._render_ip_details(event.ip)

    # ----- actions --------------------------------------------------------

    def action_refresh(self):
        region = self.query_one("#region-select", Select).value
        vpc = self.query_one("#vpc-select", Select).value
        if self._selected_subnet and region is not Select.BLANK:
            self.load_ip_map(region, self._selected_subnet)
        elif vpc is not Select.BLANK and region is not Select.BLANK:
            self.load_subnets(region, vpc)
        elif region is not Select.BLANK:
            self.load_vpcs(region)
        else:
            self.load_regions()


def main():
    VpcFragTUI().run()


if __name__ == "__main__":
    main()
