# astropix-python

FAKE VANDALISM!

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
* Scans

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

# How to use the astropix2 module
Astropix-py is a module with the goal of simplifying and unifying all of the diffrent branches and modulles into a single module which can be easily worked with. 
The goal is to provide a simple interface where astropix can be configured, initalized, monitored, and iterfaced with without having to modify source files or copy and paste code from various repositories. 

Although we aim to maintain compatibility with older branches, that will not be possible in all cases (for example the asic.py module). When this happens the original files will be preserved to maintain backwards compatibility and directions and information for moving over to the new interface.

## Directions for use:
Must go in this order!!

1. Creating the instance
    - After import, call astropix2().
    - Usage: `astropix2([none required], clock_period_ns: int, inject: bool)`
    - optional arguments: 
        - clock_period_ns, default 10
        - inject, default `False`. When true configures the pixels to accept an injection voltage
2. Initializing voltages
    - call `astro.init_voltages([none required] slot, vcal, vsupply, vthreshold, [optional] dacvals)`
    - slot: Usually 4, tells chip where the board is
    - vcal: calibrated voltage. Usually 0.989
    - vsupply: voltage to gecco board, usually 2.7
    - vthreshold: ToT threshold voltage. Usually 1.075 ish    
    - optional, dacvals: if you want to configure the dac values, do that here
3. Initalizing the ASIC
    - call `astro.asic_init()`
    - Usage: `astro.asic_init(yaml:str, [opt] dac_setup: dict, bias_setup: dict, digital_mask: str)`
    - Optional arguments:
        - yaml: string of name of configuration .yml file in /config/*.yml. If none given command-line, default set to config/testconfig.yml
        - dac_setup: dictionary of values which will be used to change the defalt dac settings. Does not need to have a complete dictionary, only values that you want to change. Default None
        - bias_setup: dictionary of values which will be used to change the defalt bias settings. Does not need to have a complete dictionary, only values that you want to change. Default None
        - digital_mask: text data of 1s and 0s in a 35x35 grid (newline seperated rows) specifying what pixels are on and off. If not specified chip will be in analog mode
4. Initalizing injector board (optional)
    - call `astro.init_injection()`
    - Has following options and defaults:
        - dac_settings:tuple[int, list[float]] = (2, [0.4, 0.0])
        - position: int = 3, position in board, same as slot in init_voltages().
        - inj_period:int = 100 
        - clkdiv:int = 400
        - initdelay: int = 10000 
        - cycle: float = 0
        - pulseperset: int = 1
5. enable SPI
    - `astro.enable_spi()`
    - takes no arguments

Useful methods:

astro.hits_present() --> bool. Are thre any hits on the board currently?

astro.get_readout() --> bytearray. Gets bytestream from the chip

astro.decode_readout(readout, [opt] printer) --> list of dictionaries. Printer prints the decoded values to terminal

astro.write_conf_to_yaml(<outputName>) --> write configuration settings to *.yml

astro.start_injection() and astro.stop_injection() are self explainatory

## Usage of beam_test.py

beam_test.py is a rewritten version of beam_test.py which removes the need for asic.py, and moves most configuration to command arguments.
It has the ability to:
- Save csv files
- Plot hits in real time
- Configure threshold and injection voltages 
- Enable digital output based on pixel masks 

CAUTION : try not to pass arguments to astropix.py as numpy objects - if looping through a numpy array, typecast to int, float, etc for the argument call or features may not work as intended (ie - pixels may not be activated/deactivated as expected)

Options:
| Argument | Usage | Purpose | Default |
| :--- | :--- | :---  | :--- |
| `-n` `--name` | `-n [SOMESTRING]` | Set additional name to be added to the timestamp in file outputs | None |
| `-o` `--outdir`| `-o [DIRECTORY]` | Directory to save all output files to. Will be created if it doesn't exist. | `./` |
| `-y` `--yaml`| `-y [NAME]` | Name of configuration file, assuming config/*.yml where * is passed. If not specified, uses config/testconfig.yml and disables all pixels | `testconfig` |
| `-c` `--saveascsv` | `-c`         | Toggle saving csv files on and off | Does not save csv |
| `-s` `--showhits` | `-s`          | Display hits in real time | Off |
| `-p` `--plotsave` | `-p`          | Saves real time plots as image files. Stored in outdir. | Does not save plots |
| `-t` `--threshold`| `-t [VOLTAGE]`| Sets digital threshold voltage in mV. | `100mV` |
| `-i` `--inject`| `-i [COL]`       | Toggles injection on or off at specified column. Injects 300mV unless specified. | Off|
| `-v` `--vinj` | `-v [VOLTAGE]`    | Sets voltage of injection in mV. Does not enable injection. | `300mV` |
| `-M` `--maxruns` | `-M [int]`     | Sets the maximum number of readouts the code will process before exiting. | No maximum |
| `-E` `--errormax`| `-E [int]`     | Amount of index errors encountered in the decode before the program terminates. | `0` |
| `-a` `--analog` | `-a [COL]`      | Enable analog output on specified column | `None` |
| `-L` `--loglevel` | `-L [D,I,E,W,C]`| Loglevel to be stored. Applies to both console and file. Options: D - debug, I - info, E - error, W - warning, C - critical | `I` |
| `--timeit` | `--timeit`           | Measures the time it took to decode and store a hitstream. | Off |


