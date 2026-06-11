# Installation

## uv tool

```bash
uv tool install git+https://github.com/sr-codefreak/personal-assistant-bridge.git
```

## pipx

```bash
pipx install git+https://github.com/sr-codefreak/personal-assistant-bridge.git
```

## Source checkout

```bash
git clone git@github.com:sr-codefreak/personal-assistant-bridge.git
cd personal-assistant-bridge
uv sync --all-extras --dev
uv run ai-subscription-bridge doctor
```
