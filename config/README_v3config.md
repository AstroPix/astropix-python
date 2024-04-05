# Notes about optimal v3 running

The orignal "default" settings as derived from simulation in `testconfig_v3.yml`

DAC optimization studies for current dacs (`idacs`) from GSFC and Hiroshima U resulted in the following optimized values, which are reflected in the central files `config_v3_none.yml`, `config_v3_all.yml`, and `config_v3_c0_r0.yml`

> blres:              [6, 0]
> nu1:                [6, 0]
> vn1:                [6, 20]
> vnfb:               [6, 3]
> vnfoll:             [6, 1]
> nu5:                [6, 0]
> nu6:                [6, 0]
> nu7:                [6, 0]
> nu8:                [6, 0]
> vn2:                [6, 0]
> vnfoll2:            [6, 10]
> vnbias:             [6, 10]
> vpload:             [6, 5]
> nu13:               [6, 60]
> vncomp:             [6, 2]
> vpfoll:             [6, 60]
> nu16:               [6, 0]
> vprec:              [6, 60]
> vnrec:              [6, 30]

These central configuration files run in HIGH DYNAMIC RANGE MODE (the `blres` value `DisHiDR == 0` ). The chip can also be run in HIGH GAIN MODE by disabling this value. 
