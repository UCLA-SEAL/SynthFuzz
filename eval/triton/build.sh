#!/bin/bash

set -e

PROJ_SHA="678bbe212a282121f718bbaff3ad55afbf3c0e7c"

cd /workdir

if [ ! -d "triton" ]; then
    echo "Cloning Triton..."
    git clone https://github.com/openai/triton.git
fi

cd triton

# Check if the specific commit is already checked out
if [ "$(git rev-parse HEAD)" != "$PROJ_SHA" ]; then
    echo "Checking out specific commit ($PROJ_SHA)..."
    git checkout $PROJ_SHA
fi

echo "Checking if patch is already applied..."
patchfile="/synthfuzz/eval/triton/0001-Enable-Coverage.patch"

# Extract the commit message from the patch file
patch_commit_message=$(git format-patch -1 --stdout $patchfile | grep -i 'Subject:' | cut -d ':' -f 2- | sed 's/^ //')

# Retrieve the last commit message
last_commit_message=$(git log -1 --pretty=%B)

# Compare the commit messages
if [ "$patch_commit_message" != "$last_commit_message" ]; then
    echo "Patch has not been applied. Applying now..."
    git am $patchfile
else
    echo "Patch has already been applied."
fi

echo "Building Triton..."
export TRITON_BUILD_WITH_CLANG_LLD=true
export TRITON_BUILD_WITH_CCACHE=true
pip install -e python