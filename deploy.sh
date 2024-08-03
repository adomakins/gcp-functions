#!/bin/bash

# Check if a function name was provided
if [ $# -eq 0 ]; then
    echo "Error: No function name provided."
    echo "Usage: ./deploy.sh <function-name>"
    exit 1
fi

# Get the function name from the first argument
FUNCTION_NAME=$1

# Check if the function directory exists
if [ ! -d "$FUNCTION_NAME" ]; then
    echo "Error: Function directory '$FUNCTION_NAME' does not exist."
    exit 1
fi

# Change to the function directory
cd "$FUNCTION_NAME" || exit

# Initialize variables
RUNTIME=""
ENTRY_POINT=""

# Check for main.py
if [ -f "main.py" ]; then
    RUNTIME="python311"
    ENTRY_POINT="main"
# Check for index.js
elif [ -f "index.js" ]; then
    RUNTIME="nodejs20"
    ENTRY_POINT="$FUNCTION_NAME"
else
    echo "Error: Neither main.py nor index.js found in the function directory."
    exit 1
fi

# Deploy the function
echo "Deploying function with runtime: $RUNTIME"
gcloud functions deploy "$FUNCTION_NAME" \
    --runtime "$RUNTIME" \
    --trigger-http \
    --entry-point "$ENTRY_POINT" \
    --allow-unauthenticated \
    --ignore-file=../.gcloudignore \
    --service-account=836705719816-compute@developer.gserviceaccount.com

# Change back to the original directory
cd ..
