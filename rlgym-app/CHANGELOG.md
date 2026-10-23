# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- A Configs page: create named environment configs, see how far along each one is, and delete them.
- A config editor: open a config to rename it, pick a discovered component for each part of the env, and fill in its constructor arguments in a form generated from its signature. Required parts and arguments that are still empty are highlighted.
- Export a saved config from its editor as a Python snippet (the imports and the `RLGym(...)` call), a runnable script that builds the env and resets it once, or JSON. Preview it, copy it, or save it to a file.

## [0.2.0] - 2026-10-17

### Added

- A Settings page: choose the Python interpreter of your RLGym project (type its path or pick it with "Browse…") and the modules to scan for components. The page shows the interpreter's Python and rlgym-api versions, or why it can't be used.
- A Components page: browse the RLGym components found in your modules, grouped by kind (state mutators, observation builders, rewards...), with each one's docstring and constructor parameters. Modules that fail to import are listed with their error, and "Rescan" picks up code changes.

## [0.1.0] - 2026-10-17

### Added

- A "What's new" button next to the update button: see what an update changes before downloading it.

## [0.0.4] - 2026-10-09

### Added

- More generic text
- A little diagram for style purposes

## [0.0.3] - 2026-10-09

### Added

- A good looking home page with a little explanation and extras

## [0.0.2] - 2026-10-09

### Fixed

- Backend was not being built correctly

## [0.0.1] - 2026-10-09

### Added

- An auto updating mechanism, in order to update the application from the application rather than redownloading.