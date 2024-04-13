# Using Wix to create the MSI installer

Need to install Wix and the WixToolset.UI.wixext extension

_Wix:_
`dotnet tool install --global wix`

_WixToolset.UI.wixext Extension:_
`wix extension add -g WixToolset.UI.wixext`

With Wix installed, you need to generate the Wix XML.

`python generate_wix.py --folder <deploy output> --version <version of JG>`

This will generate the WXS file and a "wix_data.p" file which are used to build the installer.

From there, run wix:

`wix build -src joystick_gremlin.wxs -ext WixToolset.UI.wixext`