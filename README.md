# astropix-python

Python based lightweight cross-platform tool to control the GECCO System, based on [ATLASPix3_SoftAndFirmware](https://git.scc.kit.edu/jl1038/atlaspix3)

To interact with the FTDI-Chip the ftd2xx package is used, which provides a wrapper around the proprietary D2XX driver.
The free pyftdi driver currently does not support the synchronous 245 FIFO mode.  
For bit manipulation the bitstring package is used.

Features:
* Write ASIC config (SR and SPI)
* Configure Voltageboards (+offset cal)
* Configure Injectionboard
* Read/Write single registers
* SPI/QSPI Readout
* Import/export chip config from/to yaml

Work in progress:
* GUI

## Installation

Requirements:
* Python >= 3.9
* packages: ftd2xx, async-timeout, bitstring 
* D2XX Driver

```shell
$ git clone git@github.com:nic-str/astropix-python.git
$ cd astropix-python

# Create venv
$ python3 -m venv astropix-venv
$ source astropix-venv/bin/activate

# Install Requirements
$ pip install -r requirements.txt
```

### Windows

D2XX Driver should be pre-installed.

### Linux

Install D2XX driver: [Installation Guide](https://ftdichip.com/wp-content/uploads/2020/08/AN_220_FTDI_Drivers_Installation_Guide_for_Linux-1.pdf)

Check if VCP driver gets loaded:
    
    sudo lsmod | grep -a "ftdi_sio"

If yes, create a rule e.g., 99-ftdi-nexys.rules in /etc/udev/rules.d/ with the following content to unbid the VCP driver and make the device accessible for non-root users:

    ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010",\
    PROGRAM="/bin/sh -c '\
        echo -n $id:1.0 > /sys/bus/usb/drivers/ftdi_sio/unbind;\
        echo -n $id:1.1 > /sys/bus/usb/drivers/ftdi_sio/unbind\
    '"

    ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010",\
    MODE="0666"

Reload rules with:

    sudo udevadm trigger

Create links to shared lib:

    sudo ldconfig

### Mac
See [FTDI Mac OS X Installation Guide](https://www.ftdichip.com/Support/Documents/InstallGuides/Mac_OS_X_Installation_Guide.pdf) D2XX Driver section from page 10.

# How to use the astropixRun wrapper
Astropix.py is a module with the goal of simplifying and unifying all of the diffrent branches and modules into a single warpper which can be easily worked with. 
The goal is to provide a simple interface where astropix can be configured, initalized, monitored, and interfaced with without having to modify source files or copy and paste code from various repositories. 

## Directions for use:

1. Creating the instance
    - After import, call astropixRun().
    - Usage: `astropixRun([none required], [opt] inject, offline)`
    - optional arguments: 
        - inject: [row, col] of pixel where injection will be enabled. If no argument provided, no pixel enabled for injection
        - offline: Default FALSE. Set to TRUE to interface with an astropixRun object but not collect data (ex. to only decode an existing file)
2. Initializing voltages
    - call `astro.init_voltages([none required], [opt] vcal, vsupply, vthreshold, dacvals)`
    - Optional arguments:
        - vcal: calibrated voltage. Default 0.989
        - vsupply: voltage to gecco board. Default 2.7
        - vthreshold: ToT threshold voltage. Default value provided in yml (or 100 if not provided in yml)   
        - dacvals: if you want to configure the dac values, do that here
3. Initalizing the ASIC
    - call `astro.asic_init()`
    - Usage: `astro.asic_init(yaml, [opt] dac_setup, bias_setup, analog_col)`
    - Required arguments:
        - yaml: string of name of configuration .yml file in /config/*.yml
    - Optional arguments:
        - dac_setup: dictionary of values which will be used to change the defalt dac settings (from yml config). Does not need to have a complete dictionary, only values that you want to change. Default None
        - bias_setup: dictionary of values which will be used to change the defalt bias settings. Does not need to have a complete dictionary, only values that you want to change. Default None
        - analog_col: column of pixel in row0 to enable analog output. Default None (no analog output)
4. Initalizing injector board (optional)
    - call `astro.init_injection()`
    - Usage: `astro.init_injection([none required], [opt] inj_voltage, inj_period, clkdiv, initdelay, cycle, pulseperset, onchip)`
    - Optional arguments:
        - inj_voltage: Amplitude of injected square wave. Default provided in yml (or 300 [mV] if not provided in yml)
        - inj_period: period of injection. Default 100
        - clkdiv: Number of clock divisions. Default 300
        - initdelay: Initialization delay. Default 100
        - cycle: Default 0
        - pulseperset: Number of injection pulses per cycle. Default 1
        - onchip: bool regarding injeciton pulse generation. Default FALSE (generated with card in GECCO board. If TRUE, generated in periphery on chip - only valid for astropix v3 and higher) 
5. enable SPI
    - `astro.enable_spi()`
    - takes no arguments
6. Send configuration to chip
    - `astro.asic_configure()`
    - takes no arguments

Useful methods:

astro.get_readout() --> bytearray. Gets bytestream from the chip

astro.decode_readout(readout, [opt] printer) --> list of dictionaries. Printer prints the decoded values to terminal

astro.write_conf_to_yaml(<outputName>) --> write configuration settings to *.yml

astro.start_injection() and astro.stop_injection() are self explainatory

## Usage of beam_test.py

beam_test.py has the ability to:
- Save csv files
- Plot hits in real time
- Configure threshold and injection voltages 
- Enable digital output based on pixel masks 

CAUTION : try not to pass arguments to astropix.py as numpy objects - if looping through a numpy array, typecast to int, float, etc for the argument call or features may not work as intended (ie - pixels may not be activated/deactivated as expected)

Options:
| Argument | Usage | Purpose | Default |
| :--- | :--- | :---  | :--- |
| `-n` `--name` | `-n [SOME_STRING]` | Set additional name to be added to the timestamp in file outputs | None |
| `-o` `--outdir`| `-o [SOME_STRING]` | Directory to save all output files to. Will be created if it doesn't exist. | `./` |
| `-y` `--yaml`| `-y [NAME]` | Name of configuration file, assuming config/*.yml where * is passed. If not specified, uses config/testconfig.yml and disables all pixels | `testconfig` |
| `-V` `--chipVer` | `-V [SOME_INT]` | Defines chip version and available settings. Should match yml file | 2 |
| `-c` `--saveascsv` | `-c`         | Toggle saving csv files on and off | Does not save csv |
| `-s` `--showhits` | `-s`          | Display hits in real time | Off |
| `-p` `--plotsave` | `-p`          | Saves real time plots as image files. Stored in outdir. | Does not save plots |
| `-t` `--threshold`| `-t [VOLTAGE]`| Sets digital threshold voltage in mV. | `100mV` |
| `-i` `--inject`| `-i [COL]`       | Toggles injection on or off at specified column. Injects 300mV unless specified. | Off|
| `-v` `--vinj` | `-v [VOLTAGE]`    | Sets voltage of injection in mV. Does not enable injection. | `300mV` |
| `-M` `--maxtime` | `-M [float]`     | Sets the length of time for data collection, in minutes. | No maximum |
| `-r` `--maxruns` | `-r [int]`     | Sets the maximum number of readouts the code will process before exiting. | No maximum |
| `-E` `--errormax`| `-E [int]`     | Amount of index errors encountered in the decode before the program terminates. | `0` |
| `-a` `--analog` | `-a [COL]`      | Enable analog output on specified column | `None` |
| `-L` `--loglevel` | `-L [D,I,E,W,C]`| Loglevel to be stored. Applies to both console and file. Options: D - debug, I - info, E - error, W - warning, C - critical | `I` |
| `--timeit` | `--timeit`           | Measures the time it took to decode and store a hitstream. | Off |


