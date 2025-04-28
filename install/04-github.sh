#!/bin/bash
# setup_github.sh - Clone GitHub repository and set up project (non-interactive)

# Check for repository URL argument
if [ -z "$1" ]; then
    echo "ERROR: GitHub repository URL is required"
    echo "Usage: $0 <repository_url> [install_directory]"
    exit 1
fi

# Get arguments
REPO_URL="$1"
INSTALL_DIR="/root/raptor"

# Validate repository URL format
if ! [[ "$REPO_URL" =~ ^(https://github.com/|git@github.com:)[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(.git)?$ ]]; then
    echo "ERROR: Invalid GitHub repository URL format: $REPO_URL"
    echo "Valid formats:"
    echo "  - https://github.com/username/repository.git"
    echo "  - git@github.com:username/repository.git"
    exit 1
fi

echo "Setting up GitHub repository: $REPO_URL"
echo "Installation directory: $INSTALL_DIR"

# Test SSH connection if using SSH URL
if [[ "$REPO_URL" =~ ^git@github.com: ]]; then
    echo "Testing SSH connection to GitHub..."
    if ! ssh -T git@github.com -o StrictHostKeyChecking=no -o BatchMode=yes 2>&1 | grep -q "successfully authenticated"; then
        echo "ERROR: GitHub SSH authentication test failed"
        echo "Make sure your SSH keys are properly set up before running this script"
        exit 1
    else
        echo "GitHub SSH connection successful"
    fi
fi

# Create installation directory if it doesn't exist
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory already exists"
    
    # Check if it's a git repository
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "Existing git repository found. Updating..."
        cd "$INSTALL_DIR"
        
        # Check if the remote URL matches
        CURRENT_URL=$(git config --get remote.origin.url)
        if [ "$CURRENT_URL" != "$REPO_URL" ]; then
            echo "ERROR: Existing repository has different remote URL:"
            echo "  Current: $CURRENT_URL"
            echo "  Requested: $REPO_URL"
            echo "Please remove the directory or use the correct URL"
            exit 1
        fi
        
        # Pull latest changes
        git pull
        RESULT=$?
        if [ $RESULT -ne 0 ]; then
            echo "ERROR: Failed to update repository"
            exit 1
        fi
    else
        echo "ERROR: Directory exists but is not a git repository: $INSTALL_DIR"
        exit 1
    fi
else
    echo "Creating installation directory and cloning repository..."
    mkdir -p "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    RESULT=$?
    if [ $RESULT -ne 0 ]; then
        echo "ERROR: Git clone failed"
        exit 1
    fi
fi

# Change to installation directory
cd "$INSTALL_DIR"

# Set up Python environment
echo "Setting up Python environment..."
if [ -f "requirements.txt" ]; then
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install requirements
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install Python requirements"
        exit 1
    else
        echo "Python requirements installed successfully"
    fi
    echo "Installing RAPTOR library"
    pip install -e .
    if [ $? -ne 0 ]; then
	    echo "ERROR: Failed to install Raptor code"
	    exit 1
    fi
else
    echo "No requirements.txt found. Skipping Python setup."
fi


# Check if the activation line already exists in .bashrc
if grep -q "source /root/raptor/env/bin/activate" /root/.bashrc; then
    echo "Virtual environment activation already exists in .bashrc"
else
    # Add the activation line to .bashrc
    echo "" >> /root/.bashrc
    echo "# Activate Python virtual environment" >> /root/.bashrc
    echo "source /root/raptor/venv/bin/activate" >> /root/.bashrc

    echo "Added virtual environment activation to .bashrc"
    echo "The virtual environment will be activated on next login"
fi

echo "GitHub repository/python environment setup complete!"


exit 0
