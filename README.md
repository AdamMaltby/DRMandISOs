# getDellRepoManComponentsAndISOs

## SYNOPSIS:
getDellRepoManComponentsAndISOs is designed to get Dell Repository Manager component links and SUU ISOs. Optionally will download.

## DESCRIPTION:
Designed for sites where DRM sits in a dark site (no internet) and components, firmwares, plugins etc have to be pulled manually from Dells Website. This system reads various catalogues and pages to extrapolate the latest links for download off all required components and either presents relevant links back to the user or downloads to a storage folder automatically.

## HELP
Optional arguments:

    -h, --help          show this help message and exit

    -wb [Component [Component ...]], --whichBits [Component [Component ...]]
                        Supplied as a space separated list. Default is
                        displayOnly. (default: display-Only)

CLI and File logging options:

    -v, --verbose       Verbose display output to the CLI, default is none
                        when not specified. Add v's (max 6) to increase
                        verbosity. if unset, will set to WARNING. (default: 0)
    -l, --logfile       Log output to file, in same directory as script.
                        Logging will rotate every 1mb of logging unless
                        deleted. Logging level will be based on -v argument.
                        (default: False)

Component Download Options:

    -dp DP, --downloadToPath DP
                        If unset or used but no path specified, saves will
                        default to this script launch directory. Ignored if
                        -wb argument contains display-Only option. (default:
                        .)

whichBits Component Options List for Display/Download using -wb / --whichBits:

    displayOnly         The default choice if the argument is not passed. Can
                        be used with other choices to limit output. Not using
                        displayOnly when using -wb in conjucntion with
                        components invokes downloading automatically.
    drminstaller-linux  Display or download the current DRM Installer for
                        Linux.
    drminstaller-windows
                        Display or download the current DRM Installer for
                        Windows.
    plugins             Display or download DRM plugins only.
    suu-linux           Display or download the SUU for Linux inband firmware
                        updates
    suu-windows         Display or download the SUU for Windows inband and oob
                        firmware updates

Proxy Details - note for security, password is promtped for during running. Not an parameter option prior to launch:

    -pa PA, --proxyaddress PA
                        Specify Proxy Address inc port if not port 80 or 443,
                        e.g. myproxy.dom.local:8080 or 192.168.234.254
                        (default: None)
    -pu PU, --proxyusername PU
                        Enter Proxy Username (default: None)

## EXAMPLE:
python getDellRepoManComponentsAndISOs.py -l -v -wb displayOnly drminstaller-linux suu-linux

## EXAMPLE:
python getDellRepoManComponentsAndISOs.py -wb drminstaller-windows suu-windows plugins -pa 192.168.268.254:3128

## AUTHOR:
Adam Maltby
