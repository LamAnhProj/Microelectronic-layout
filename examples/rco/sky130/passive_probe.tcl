# Isolated SKY130 MIM and high-R poly PCells for physical-flow audit.
load rco_passive_probe
box values 0um 0um 0um 0um
magic::gencell sky130::sky130_fd_pr__cap_mim_m3_2 CUNIT w 4.5 l 4.5
box values 30um 0um 30um 0um
magic::gencell sky130::sky130_fd_pr__res_xhigh_po_1p41 RDELAY w 1.41 l 330
select top cell
box values -20um -20um 60um 110um
drc style drc(full)
drc check
drc catchup
drc count total
foreach cell [cellname list children rco_passive_probe] {
    pushstack $cell
    save $cell
    popstack
}
save rco_passive_probe
extract all
ext2spice lvs
ext2spice -o rco_passive_probe.spice
gds write rco_passive_probe.gds
puts "GDS_FEEDBACK_COUNT=[feedback count]"
feedback save gds_feedback.txt
quit -noprompt
