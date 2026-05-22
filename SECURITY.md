# Security Policy

## Supported Versions

Security updates are provided for the latest public versions of the add-ons in **Andre's HA-Addons**.

Because this repository contains multiple Home Assistant add-ons, security fixes generally target the latest release of the affected add-on and the current `main` branch.

| Version / Branch | Supported |
| ---------------- | --------- |
| `main`           | Yes       |
| Latest releases  | Yes       |
| Older releases   | No        |

## Reporting a Vulnerability

Please do not open a public GitHub issue for security vulnerabilities.

Report vulnerabilities privately using GitHub Security Advisories if available, or contact the maintainer directly.

Please include:

- affected add-on
- affected version, branch, or commit
- clear description of the issue
- steps to reproduce
- possible impact
- whether exploitation is local or remote
- relevant logs, screenshots, or proof-of-concept details
- suggested mitigation, if known

## Scope

Security reports are especially relevant for issues involving:

- unauthorized access
- exposure of Home Assistant tokens or credentials
- unsafe Home Assistant add-on behavior
- command injection
- unsafe handling of user configuration
- insecure network behavior
- unexpected control of connected equipment
- incorrect exposure or manipulation of Home Assistant entity data

## Safety Notice

Some add-ons in this repository interact with real equipment or energy-related control logic. Security and safety can overlap when an issue could cause unexpected device behavior, expose credentials, or provide incorrect control data.

Please report such issues responsibly and with enough detail to allow proper investigation.
