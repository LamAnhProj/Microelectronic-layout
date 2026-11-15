"""Render an evidence-scoped RCO RC, threshold, phase, and trim lesson.

Run on the Mac from the repository root with:
  uv run --no-project --with matplotlib --with numpy python examples/rco/waveform_lesson.py

The first two figures use saved Mac artifacts. The RC comparison in figure
three is an explicit teaching model, not a post-layout RCO simulation.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "knowledge" / "figures"
SKY = ROOT / "runs/rco/e92a209b-9c13-40fc-85b3-df4c55c60c7c"
GF_COUPON = ROOT / "runs/rco/four_mim/gf180/c0f4b133-ff92-4352-899b-269b7e90c866"
GF_SWEEP = ROOT / "runs/rco/sweeps/9ca5bc14-7bc1-47ae-953c-ab3863046d13"
VTC = ROOT / "runs/rco/waveform_lesson/sky130_vtc"
COLORS = {"RC0": "#087e8b", "RC1": "#d88021", "RC2": "#8956a5", "CLK": "#2e8b57"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric_rows(path: Path, columns: int) -> list[list[float]]:
    rows = []
    for line in path.read_text().splitlines()[1:]:
        words = line.split()
        if len(words) == columns:
            rows.append([float(word) for word in words])
    if len(rows) < 100:
        raise RuntimeError(f"Too few samples in {path}")
    return rows


def crossing(rows: list[list[float]], col: int, threshold: float,
             direction: str) -> list[float]:
    result = []
    for a, b in zip(rows, rows[1:]):
        crossed = (a[col] < threshold <= b[col] if direction == "rise"
                   else a[col] > threshold >= b[col])
        if crossed:
            result.append(a[0] + (threshold - a[col]) *
                          (b[0] - a[0]) / (b[col] - a[col]))
    return result


def vtc_trip(source_netlist: Path) -> tuple[float, list[list[float]], Path]:
    """DC sweep the exact nominal INV1 model/geometry from the saved RCO."""
    lines = source_netlist.read_text().splitlines()
    mos = []
    for name in ("XMINV1_N", "XMINV1_P"):
        words = next(line.split() for line in lines if line.startswith(name + " "))
        words[1:3] = ["out", "in"]
        mos.append(" ".join(words))
    library = next(line for line in lines if line.startswith(".lib "))
    VTC.mkdir(parents=True, exist_ok=True)
    deck = VTC / "vtc.spice"
    deck.write_text("\n".join([
        "* DC VTC of the saved RCO INV1 MOS pair; 25 C, nominal TT",
        library, ".temp 25", "VDD vdd 0 1.8", "VIN in 0 0", *mos,
        ".control", "dc VIN 0 1.8 0.001", "set wr_singlescale",
        "set wr_vecnames", "wrdata vtc.dat v(out)", "quit", ".endc", ".end", ""
    ]))
    result = subprocess.run(["ngspice", "-b", deck.name], cwd=VTC,
                            capture_output=True, text=True, timeout=120)
    (VTC / "vtc.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("ngspice DC VTC failed; inspect vtc.log")
    rows = numeric_rows(VTC / "vtc.dat", 2)
    for a, b in zip(rows, rows[1:]):
        delta_a, delta_b = a[1] - a[0], b[1] - b[0]
        if delta_a >= 0 >= delta_b:
            trip = a[0] - delta_a * (b[0] - a[0]) / (delta_b - delta_a)
            return trip, rows, deck
    raise RuntimeError("DC VTC did not cross Vout = Vin")


def verified_inputs() -> tuple[dict, list[list[float]], dict, dict, Path]:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise RuntimeError("The lesson requires the native arm64 Mac")
    sky = json.loads((SKY / "report.json").read_text())
    wave = SKY / "waveform.dat"
    if (sky.get("host") != {"system": "Darwin", "arch": "arm64"} or
            sky.get("status") != "simulated" or sky.get("process") != "sky130" or
            sky.get("code") != 154 or sky.get("schematic") != "xschem" or
            sha256(wave) != sky.get("waveform_sha256") or
            sha256(SKY / "rco.spice") != sky.get("netlist_sha256")):
        raise RuntimeError("SKY schematic waveform provenance failed")
    coupon = json.loads((GF_COUPON / "report.json").read_text())
    rcx = GF_COUPON / "rcx" / "rco_four_mim_rcx.spice"
    if (coupon.get("status") != "passed" or
            coupon.get("host") != {"system": "Darwin", "arch": "arm64"} or
            sha256(rcx) != coupon["checks"]["rcx"]["netlist_sha256"] or
            coupon["checks"]["rcx"]["extracted_resistors"] != 1 or
            coupon["checks"]["rcx"]["extracted_coupling_capacitors"] != 11):
        raise RuntimeError("GF four-MIM RCX provenance failed")
    cap_counts = {"inter_node_nonzero": 0, "ground_nonzero": 0, "zero_value": 0}
    for line in rcx.read_text().splitlines():
        if not line.startswith("C"):
            continue
        _, left, right, value = line.split()
        if float(value.removesuffix("f")) == 0:
            cap_counts["zero_value"] += 1
        elif left.startswith("GND") or right.startswith("GND"):
            cap_counts["ground_nonzero"] += 1
        else:
            cap_counts["inter_node_nonzero"] += 1
    if cap_counts != {"inter_node_nonzero": 5, "ground_nonzero": 3,
                      "zero_value": 3}:
        raise RuntimeError("GF coupon capacitor classification changed")
    coupon["lesson_capacitor_classification"] = cap_counts
    sweep = json.loads((GF_SWEEP / "report.json").read_text())
    if (sweep.get("status") != "measured" or sweep.get("process") != "gf180" or
            sweep.get("bank_style") != "balanced" or len(sweep["points"]) != 512 or
            sweep.get("failures") or sweep.get("reversed_steps")):
        raise RuntimeError("Complete GF balanced sweep is unavailable")
    for code, point in enumerate(sweep["points"]):
        run = ROOT / "runs" / "rco" / point["run_id"] / "report.json"
        if (point["code"] != code or sha256(run) != point["report_sha256"] or
                json.loads(run.read_text()).get("host") !=
                {"system": "Darwin", "arch": "arm64"}):
            raise RuntimeError(f"GF sweep code {code} provenance failed")
    return sky, numeric_rows(wave, 5), coupon, sweep, rcx


def decorate(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", pad=13)
    ax.grid(alpha=0.15)
    ax.spines[["top", "right"]].set_visible(False)


def network_figure(coupon: dict, rcx: Path) -> Path:
    fig, (ax, excerpt) = plt.subplots(1, 2, figsize=(15, 5.6),
                                      gridspec_kw={"width_ratios": [1.2, 1]})
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("1 · Where parasitics attach", loc="left", fontsize=16, fontweight="bold")
    def wire(x1, y1, x2, y2, color="#334155", lw=2):
        ax.plot([x1, x2], [y1, y2], color=color, lw=lw, solid_capstyle="round")
    def box(x, y, w, h, label, color):
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                               facecolor=color, edgecolor="#334155", lw=1.2)
        ax.add_patch(patch);ax.text(x+w/2,y+h/2,label,ha="center",va="center",fontsize=10,fontweight="bold")
    def resistor(x1, x2, y, label):
        step=(x2-x1)/8
        xs=[x1+i*step for i in range(9)]
        ys=[y,y+.23,y-.23,y+.23,y-.23,y+.23,y-.23,y+.23,y]
        ax.plot(xs,ys,color="#d97706",lw=2)
        ax.text((x1+x2)/2,y+.52,label,ha="center",fontsize=10,color="#92400e")
    def cap(x, top, bottom, label, color="#0891b2"):
        wire(x,top,x,(top+bottom)/2+.16,color)
        wire(x,bottom,x,(top+bottom)/2-.16,color)
        mid=(top+bottom)/2
        wire(x-.25,mid+.16,x+.25,mid+.16,color)
        wire(x-.25,mid-.16,x+.25,mid-.16,color)
        ax.text(x+.36,mid,label,va="center",fontsize=10,color=color)
    box(.15,3.56,1.18,.85,"driver\nINV", "#dbeafe")
    wire(1.33,4,1.72,4);resistor(1.72,3.15,4,"Rdelay · source")
    wire(3.15,4,3.55,4);resistor(3.55,4.8,4,"Rwire · PEX")
    wire(4.8,4,9.05,4)
    box(9.05,3.56,.78,.85,"next\nINV","#dbeafe")
    ax.scatter([5.35],[4],s=65,color="#dc2626",zorder=4)
    ax.text(5.35,4.35,"RC node",ha="center",fontsize=11,color="#b91c1c",fontweight="bold")
    cap(5.55,4,1.05,"Cbank")
    cap(7.2,4,1.05,"Cground · PEX")
    cap(8.45,4,1.95,"Ccouple · PEX",color="#7c3aed")
    wire(5.55,1.05,7.2,1.05);ax.text(6.25,.63,"GND",ha="center",fontsize=10)
    wire(8.45,1.95,8.45,1.47,color="#7c3aed")
    ax.text(8.45,1.16,"neighbor wire (aggressor)",ha="center",fontsize=9,color="#7c3aed")
    ax.text(.2,.16,"Coupling current: i = Ccouple × d(VRC − Vaggressor)/dt",fontsize=10,color="#475569")

    excerpt.axis("off")
    excerpt.set_title("Actual extracted example · GF180 four-MIM coupon",loc="left",fontsize=13,fontweight="bold")
    lines = rcx.read_text().splitlines()
    chosen=[next(line for line in lines if line.startswith(prefix)) for prefix in ("R0 ","C0 ","C1 ")]
    excerpt.text(.02,.78,"Extracted SPICE",fontsize=11,fontweight="bold",transform=excerpt.transAxes)
    excerpt.text(.02,.64,"\n".join(chosen),fontsize=10,fontfamily="monospace",va="top",transform=excerpt.transAxes,
                 bbox={"facecolor":"#f1f5f9","edgecolor":"#cbd5e1","pad":10})
    excerpt.text(.02,.30,"R0 is on the coupon ground return.\nC0 joins two non-ground nodes (inter-node).\nC1 connects a node to ground.",
                 fontsize=10,va="top",transform=excerpt.transAxes)
    excerpt.text(.02,.06,"Coupon: 1 R; 11 C entries (5 inter-node, 3 ground, 3 zero).\nThe complete RCO bank has no PEX yet.",
                 fontsize=10,color="#991b1b",va="bottom",transform=excerpt.transAxes)
    fig.suptitle("Extracted network: read the two node names on each R and C line",fontsize=18,fontweight="bold")
    fig.tight_layout(rect=(0,0,1,.92))
    path=OUT/"rco-lesson-1-extracted-network.png";fig.savefig(path,dpi=180);plt.close(fig);return path


def waveform_figure(sky: dict, wave: list[list[float]], trip: float,
                    vtc: list[list[float]]) -> tuple[Path, dict]:
    rc0=crossing(wave,1,trip,"rise")[-3]
    rc1=next(t for t in crossing(wave,2,trip,"fall") if t>rc0)
    rc2=next(t for t in crossing(wave,3,trip,"rise") if t>rc1)
    clk=next(t for t in crossing(wave,4,.9,"rise") if t>rc0)
    clk_next=next(t for t in crossing(wave,4,.9,"rise") if t>clk+1e-7)
    period=sky["measurements"]["period_s"]
    fig=plt.figure(figsize=(15,9));gs=fig.add_gridspec(2,2,height_ratios=[1.1,.9],hspace=.35,wspace=.25)
    ax=fig.add_subplot(gs[0,:]);zoom=fig.add_subplot(gs[1,0]);vtc_ax=fig.add_subplot(gs[1,1])
    decorate(ax,"2 · Read the saved SKY130A oscillator waveform")
    time=[row[0]*1e6 for row in wave]
    for col,name in enumerate(("RC0","RC1","RC2","CLK"),1):
        ax.plot(time,[row[col] for row in wave],label=name,color=COLORS[name],lw=1.7)
    ax.axhline(trip,color="#dc2626",ls="--",lw=1,label=f"DC Vtrip = {trip:.3f} V")
    for t,label,color in ((rc0,"RC0 ↑",COLORS["RC0"]),(rc1,"RC1 ↓",COLORS["RC1"]),
                          (rc2,"RC2 ↑",COLORS["RC2"])):
        ax.axvline(t*1e6,color=color,ls=":",lw=1.5)
        ax.text(t*1e6+.025,1.88,label,rotation=90,fontsize=9,color=color,va="top")
    ax.set_xlim(rc0*1e6-.25,rc0*1e6+2.18);ax.set_ylim(-.07,2.0)
    ax.set_xlabel("Time (µs)");ax.set_ylabel("Voltage (V)");ax.legend(ncol=5,loc="lower right",fontsize=9)
    ax.text(.015,.04,f"CLK period = {period*1e6:.6f} µs  →  {sky['measurements']['frequency_hz']/1000:.3f} kHz",
            transform=ax.transAxes,fontsize=10,bbox={"facecolor":"white","alpha":.9,"edgecolor":"#cbd5e1"})
    ax.text(.61,.94,f"RC0 ↑ to RC2 ↑ = {(rc2-rc0)*1e9:.1f} ns\nPhase = {360*(rc2-rc0)/period:.1f}° of one cycle",
            transform=ax.transAxes,va="top",fontsize=10,
            bbox={"facecolor":"white","alpha":.9,"edgecolor":"#cbd5e1"})
    decorate(zoom,"Zoom: interpolate the RC0 threshold crossing")
    zoom.plot(time,[row[1] for row in wave],color=COLORS["RC0"],lw=2,label="RC0")
    zoom.axhline(trip,color="#dc2626",ls="--",label=f"Vtrip {trip:.3f} V")
    zoom.axhline(.9,color="#94a3b8",ls=":",label="VDD/2 = 0.900 V")
    zoom.scatter([rc0*1e6],[trip],color="#dc2626",s=65,zorder=4)
    zoom.annotate(f"{rc0*1e6:.6f} µs",(rc0*1e6,trip),xytext=(rc0*1e6-.23,1.27),
                  arrowprops={"arrowstyle":"->","color":"#dc2626"},fontsize=10)
    zoom.set_xlim(rc0*1e6-.32,rc0*1e6+.32);zoom.set_ylim(.35,1.4)
    zoom.set_xlabel("Time (µs)");zoom.set_ylabel("RC0 voltage (V)");zoom.legend(fontsize=9)
    decorate(vtc_ax,"Separate DC sweep: find the inverter trip point")
    vtc_ax.plot([r[0] for r in vtc],[r[1] for r in vtc],color="#1d4ed8",label="Vout(Vin)")
    vtc_ax.plot([0,1.8],[0,1.8],color="#94a3b8",ls="--",label="Vout = Vin")
    vtc_ax.scatter([trip],[trip],s=60,color="#dc2626",zorder=4)
    vtc_ax.annotate(f"({trip:.3f}, {trip:.3f}) V",(trip,trip),xytext=(1.07,1.25),
                    arrowprops={"arrowstyle":"->","color":"#dc2626"},fontsize=10)
    vtc_ax.set_xlabel("Input voltage (V)");vtc_ax.set_ylabel("Output voltage (V)")
    vtc_ax.set_xlim(0,1.8);vtc_ax.set_ylim(0,1.8);vtc_ax.legend(fontsize=9)
    fig.suptitle("Saved Mac schematic simulation · SKY130A · code 154 · nominal TT, 25 °C · no layout PEX",
                 fontsize=16,fontweight="bold")
    path=OUT/"rco-lesson-2-threshold-waveform.png";fig.savefig(path,dpi=180,bbox_inches="tight");plt.close(fig)
    metrics={"dc_trip_v":trip,"rc0_rise_crossing_us":rc0*1e6,
             "rc1_fall_crossing_us":rc1*1e6,"rc2_rise_crossing_us":rc2*1e6,
             "clock_rise_us":clk*1e6,"next_clock_rise_us":clk_next*1e6,
             "rc0_to_rc1_ns":(rc1-rc0)*1e9,"rc0_to_rc2_ns":(rc2-rc0)*1e9,
             "rc0_to_rc2_phase_deg":360*(rc2-rc0)/period,
             "clock_period_us":period*1e6,"clock_frequency_hz":sky["measurements"]["frequency_hz"]}
    return path,metrics


def behavior_figure(sweep: dict) -> tuple[Path, dict]:
    fig,(model,trim)=plt.subplots(1,2,figsize=(15,6.2),gridspec_kw={"width_ratios":[1,1.2]})
    decorate(model,"3 · Predicted effect of extra R and coupling")
    vdd=1.8;threshold=.9;times=[i*2.5 for i in range(401)] # ns
    cases=[("Base: 470 kΩ, 1.00 pF",470e3,1.00e-12,"#087e8b"),
           ("Quiet neighbor: 475 kΩ, 1.05 pF",475e3,1.05e-12,"#d88021"),
           ("Opposite edge: 475 kΩ, 1.10 pF",475e3,1.10e-12,"#8956a5")]
    model_values=[]
    for label,resistance,cap,color in cases:
        tau=resistance*cap
        volt=[vdd*(1-math.exp(-(t*1e-9)/tau)) for t in times]
        cross=tau*math.log(2)*1e9
        freq=1/(6*tau*math.log(2))/1000
        model.plot(times,volt,color=color,lw=2,label=f"{label}\n  cross {cross:.0f} ns · toy f {freq:.0f} kHz")
        model.scatter([cross],[threshold],color=color,s=50,zorder=4)
        model_values.append({"label":label,"crossing_ns":cross,"toy_frequency_khz":freq})
    model.axhline(threshold,color="#64748b",ls="--",lw=1)
    model.set_xlim(0,850);model.set_ylim(0,1.9);model.set_xlabel("Time after driver step (ns)")
    model.set_ylabel("Illustrative RC voltage (V)");model.legend(loc="lower right",fontsize=9)
    model.text(.02,.04,"Lumped teaching model: V = 1.8 × (1 − e^(−t/RC))\nT ≈ 6 × crossing time. Not the extracted RCO.",
               transform=model.transAxes,fontsize=9,bbox={"facecolor":"white","alpha":.9,"edgecolor":"#cbd5e1"})
    decorate(trim,"4 · Actual GF180 balanced-bank trim sweep")
    points=sweep["points"]
    codes=[p["code"] for p in points];freq=[p["frequency_hz"]/1000 for p in points]
    trim.plot(codes,freq,color="#087e8b",lw=1.8,label="512 nominal Mac transient runs")
    trim.axhline(512,color="#dc2626",ls="--",lw=1.2,label="512 kHz target")
    trim.scatter([117],[freq[117]],color="#dc2626",s=60,zorder=4)
    trim.annotate(f"code 117\n{freq[117]:.3f} kHz",(117,freq[117]),xytext=(185,690),
                  arrowprops={"arrowstyle":"->","color":"#dc2626"},fontsize=10)
    trim.set_xlabel("Nine-bit trim code");trim.set_ylabel("Oscillation frequency (kHz)")
    trim.set_xlim(0,511);trim.set_ylim(150,1190);trim.legend(loc="lower left",fontsize=9)
    inset=trim.inset_axes([.47,.53,.47,.37])
    near=range(112,122)
    inset.plot(list(near),[freq[i] for i in near],"o-",color="#d88021",lw=1.5)
    inset.axhline(512,color="#dc2626",ls="--",lw=1)
    inset.set_title("Zoom: individual code steps",fontsize=9)
    inset.set_xticks([112,114,116,118,120]);inset.tick_params(labelsize=8)
    inset.grid(alpha=.18)
    fig.suptitle("Behavior: extra capacitance delays an edge; trim code changes the measured period",
                 fontsize=16,fontweight="bold")
    fig.text(.5,.015,"GF sweep uses PDK device models at nominal 25 °C, 3.3 V core and 1.8 V controls. Its step variation is schematic-level; no layout parasitics were extracted.",
             ha="center",fontsize=9,color="#475569")
    fig.tight_layout(rect=(0,.04,1,.93))
    path=OUT/"rco-lesson-3-behavior-and-trim.png";fig.savefig(path,dpi=180,bbox_inches="tight");plt.close(fig)
    return path,{"model":model_values,"gf_code_116_hz":points[116]["frequency_hz"],
                 "gf_code_117_hz":points[117]["frequency_hz"],
                 "gf_code_118_hz":points[118]["frequency_hz"],
                 "gf_delta_116_to_117_hz":points[117]["frequency_hz"]-points[116]["frequency_hz"],
                 "gf_delta_117_to_118_hz":points[118]["frequency_hz"]-points[117]["frequency_hz"]}


def main() -> None:
    OUT.mkdir(parents=True,exist_ok=True)
    sky,wave,coupon,sweep,rcx=verified_inputs()
    trip,vtc,deck=vtc_trip(SKY/"rco.spice")
    figures=[network_figure(coupon,rcx)]
    waveform,observed=waveform_figure(sky,wave,trip,vtc);figures.append(waveform)
    behavior,behavior_data=behavior_figure(sweep);figures.append(behavior)
    report={"scope":"Teaching lesson; saved SKY/GF nominal schematic data, GF isolated coupon PEX, and explicit RC toy model. No full RCO layout PEX.",
            "host":{"system":platform.system(),"arch":platform.machine()},
            "builder_sha256":sha256(Path(__file__)),
            "plotting":{"matplotlib":matplotlib.__version__,"runtime":"uv --no-project temporary plotting environment"},
            "sources":{"sky_run":SKY.name,"sky_waveform_sha256":sha256(SKY/"waveform.dat"),
                       "gf_coupon_run":GF_COUPON.name,"gf_coupon_rcx_sha256":sha256(rcx),
                       "gf_sweep_run":GF_SWEEP.name,"vtc_deck_sha256":sha256(deck)},
            "coupon_capacitor_entries":coupon["lesson_capacitor_classification"],
            "observed":observed,"behavior":behavior_data,
            "figures":[{"path":str(p.relative_to(ROOT)),"sha256":sha256(p)} for p in figures]}
    path=ROOT/"knowledge"/"rco-waveform-lesson-data.json"
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"figures":[str(p) for p in figures],"observed":observed,
                      "behavior":behavior_data},indent=2))


if __name__=="__main__":
    main()
