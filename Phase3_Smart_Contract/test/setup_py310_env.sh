#!/bin/bash

echo "=== Step 1: Installing pyenv (if not installed) ==="
if ! command -v pyenv &> /dev/null; then
  curl https://pyenv.run | bash

  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
  echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
  echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
  echo 'eval "$(pyenv init -)"' >> ~/.bashrc
  echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init --path)"
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
fi

echo "=== Step 2: Installing Python 3.10.13 via pyenv ==="
pyenv install -s 3.10.13
pyenv local 3.10.13

echo "=== Step 3: Creating virtual environment with Python 3.10.13 ==="
python -m venv venv

echo "=== Step 4: Activating virtual environment ==="
source venv/bin/activate

echo "=== Step 5: Installing requirements (if requirements.txt exists) ==="
if [ -f "requirements.txt" ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "⚠️  No requirements.txt found. Skipping pip install."
fi

echo "✅ Done! Python version used:"
python --version
#chmod +x setup_py310_env.sh
#./setup_py310_env.sh
# This script sets up a Python 3.10.13 environment using pyenv and creates a virtual environment.
# It also installs the required packages from requirements.txt if it exists.