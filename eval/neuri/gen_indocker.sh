#!/bin/bash

set -xe

cd /artifact

git remote set-url origin https://github.com/ise-uiuc/neuri-artifact.git
git pull origin main

./fuzz.sh 5 neuri tensorflow xla 2h

