# Xthings Station for Home Assistant

This repository provides the community-maintained Xthings Station custom integration for Home Assistant.

It is not part of the official Home Assistant Core integrations and is not reviewed or supported by the Home Assistant project.

## Installation with HACS

1. Open HACS in Home Assistant.
2. Open **Integrations** and choose **Custom repositories** from the menu.
3. Add this repository URL:

   `https://github.com/zhangluofeng/ha-xthings-cloud-station`

4. Select **Integration** as the repository type.
5. Install **Xthings Station** and restart Home Assistant.
6. Add **Xthings Station** from **Settings > Devices & services**.

## Features

- Optional FRP remote access to the Home Assistant instance
- Optional browser-based SSO login from Xthings Cloud

This integration does not discover or control Xthings Cloud devices. It only
provides the remote-access tunnel and the SSO callback used by the station.

Xthings Station uses the `xthings_station` domain so it can run alongside
Home Assistant's built-in `xthings_cloud` integration. This domain change is
breaking: remove any existing Xthings Cloud Station integration entry and
custom component before installing this version, then add Xthings Station.

The `ha_xthings_cloud` 1.0.8 API client is bundled inside this integration
under Apache-2.0. HACS does not download a separate `ha-xthings-cloud` Python
package.

Review the code and permissions before installing. This repository is community maintained.
