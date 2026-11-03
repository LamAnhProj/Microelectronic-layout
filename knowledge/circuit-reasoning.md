# Predict before simulating

Original project note; validate process-specific claims against the actual PDK.
Reference pointers: MIT 6.012 and https://ngspice.sourceforge.io/docs.html .

For an RC lowpass with ideal source and no external load, H(s)=1/(1+sRC),
tau=RC, and f_3dB=1/(2*pi*R*C). At R=1 kohm and C=1 nF, tau=1 us and
f_3dB is about 159.155 kHz. Loading, source resistance and parasitics change this.

Determine MOS bias/operating point before applying a small-signal model. gm/Id
is efficiency in 1/V. Long-channel strong-inversion gm/Id approximately 2/Vov is
a teaching approximation, not a universal sizing law. Use process-model sweeps
at the actual length, drain/body voltages and temperature. Check headroom.

Gain estimates using gm times output resistance require a valid bias and explicit
load. Inspect supply current, regions and branch currents before trusting gain.
For feedback, define the loop/sign convention and preserve bias/loading when
breaking the loop. A transient step does not replace stability analysis across
loads and corners.

For noise, name the integration band and input/output referral. Define PSD
conventions when comparing sources. Process corners and local statistical
mismatch are different experiments; corner sweeps do not establish matching yield.
