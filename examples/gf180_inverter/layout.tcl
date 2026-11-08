proc rect {layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    paint $layer
}
proc via {x y} {
    rect via1 [expr {$x - 0.13}] [expr {$y - 0.13}] [expr {$x + 0.13}] [expr {$y + 0.13}]
}
load inverter
box values 0um 0um 0um 0um
magic::gencell gf180mcu::nfet_03v3 MN w 1 l 0.28 topc 0 botc 0 guard 0
# Bring PMOS 2 um closer to the NMOS to shorten the shared poly gate.
box values 0um 6um 0um 6um
magic::gencell gf180mcu::pfet_03v3 MP w 2 l 0.28 topc 0 botc 0 guard 0
# Poly gate extension and central contact.
rect polysilicon 0.65 1.45 1.06 6.5
rect polycontact 0.72 4.47 0.98 4.73
rect metal1 0.58 4.32 1.12 4.88
via 0.85 4.60
rect metal2 -3.5 4.4 1.05 4.8
# Device source/drain contact pads and vias.
rect metal1 0.1 0.45 0.55 1.2
rect metal1 0.9 0.45 1.35 1.2
rect metal1 0.4 6.7 0.85 8.6
rect metal1 1.2 6.7 1.65 8.6
foreach point {{0.325 0.84} {1.10 0.84} {0.625 7.65} {1.425 7.65}} {via {*}$point}
# Separate substrate and well taps.
rect pwell -2.0 0.0 1.4 1.68
rect psubdiff -1.85 0.49 -1.15 1.19
rect psubdiffcont -1.65 0.69 -1.35 0.99
rect metal1 -1.75 0.59 -1.25 1.09
via -1.50 0.84
rect nwell -2.2 6.0 2.2 9.3
rect nsubdiff -1.9 7.35 -1.1 7.95
rect nsubdiffcont -1.75 7.50 -1.25 7.80
rect metal1 -1.75 7.40 -1.25 7.90
via -1.50 7.65
# Metal2 buses and ports.
rect metal2 -2.5 0.64 0.525 1.04
rect metal2 -2.5 7.45 0.825 7.85
rect metal2 0.90 0.64 3.4 1.04
rect metal2 1.225 7.45 3.4 7.85
rect metal2 3.2 0.64 3.6 7.85
box values -3.5um 4.4um -3.1um 4.8um
label IN c metal2
port make 1
box values 3.2um 4.4um 3.6um 4.8um
label OUT c metal2
port make 2
box values -2.5um 0.64um -2.1um 1.04um
label VSS c metal2
port make 3
box values -2.5um 7.45um -2.1um 7.85um
label VDD c metal2
port make 4
select top cell
box values -10um -10um 20um 25um
drc style drc(full)
drc check
drc catchup
drc count total
foreach cell [cellname list children inverter] {pushstack $cell; save $cell; popstack}
save inverter
extract all
ext2spice lvs
ext2spice -o inverter_lvs.spice
ext2spice default
ext2spice subcircuits top on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o inverter_pex.spice
gds write inverter.gds
puts "GDS_FEEDBACK_COUNT=[feedback count]"
quit -noprompt
