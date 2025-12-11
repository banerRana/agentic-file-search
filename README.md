# fs-explorer

CLI agent that helps you explore a directory and its content.

## Installation and Usage

Clone this repository:

```bash
git clone https://github.com/run-llama/fs-explorer
cd fs-explorer
```

Install locally:

```bash
uv pip install .
```

Export a Google API key (must have access to EAP models):

```bash
export GOOGLE_API_KEY="..."
```

Run:

```bash
explore --task "Can you help me individuate, in the fs explorer codebase, what python file is responsible for file system operations?"
```

