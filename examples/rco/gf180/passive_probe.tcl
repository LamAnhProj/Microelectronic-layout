# Isolated GF180 option-B MIM and high-R poly PCells for physical-flow audit.
load rco_passive_probe
box values 0um 0um 0um 0um
magic::gencell gf180mcu::cap_mim_2p0fF CUNIT w 5 l 5
box values 40um 0um 40um 0um
magic::gencell gf180mcu::ppolyf_u_1k RDELAY w 1 l 440
select top cell
box values -20um -20um 70um 470um
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
